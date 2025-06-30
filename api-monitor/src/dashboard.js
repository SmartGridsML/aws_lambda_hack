// src/dashboard.js
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

/**
 * Dashboard API that serves aggregated metrics
 * Demonstrates advanced DynamoDB querying and data transformation
 */
exports.handler = async (event) => {
  console.log('Dashboard request:', JSON.stringify(event, null, 2));
  
  try {
    // Parse query parameters for flexible time ranges
    const queryParams = event.queryStringParameters || {};
    const hours = parseInt(queryParams.hours) || 1; // Default to last hour
    const apiHost = queryParams.api || null;
    
    // Calculate time range
    const endTime = new Date();
    const startTime = new Date(endTime.getTime() - (hours * 60 * 60 * 1000));
    
    // Query metrics from DynamoDB
    const metrics = await queryMetrics(apiHost, startTime.toISOString(), endTime.toISOString());
    
    // Transform data for frontend consumption
    const dashboardData = transformMetricsForDashboard(metrics);
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Cache-Control': 'no-cache' // Real-time data shouldn't be cached
      },
      body: JSON.stringify({
        success: true,
        data: dashboardData,
        metadata: {
          timeRange: { start: startTime, end: endTime },
          totalDataPoints: metrics.length,
          generatedAt: new Date().toISOString()
        }
      })
    };
    
  } catch (error) {
    console.error('Dashboard error:', error);
    
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        success: false,
        error: 'Failed to fetch dashboard data',
        message: error.message
      })
    };
  }
};

/**
 * Query metrics from DynamoDB with efficient pagination
 */
async function queryMetrics(apiHost, startTime, endTime) {
  const params = {
    TableName: process.env.METRICS_TABLE,
    ScanFilter: {
      timestamp: {
        AttributeValueList: [startTime, endTime],
        ComparisonOperator: 'BETWEEN'
      }
    }
  };
  
  // Add API filter if specified
  if (apiHost) {
    params.ScanFilter.pk = {
      AttributeValueList: [`api#${apiHost}`],
      ComparisonOperator: 'EQ'
    };
  }
  
  const result = await dynamodb.scan(params).promise();
  return result.Items || [];
}

/**
 * Transform raw metrics into dashboard-friendly format
 * This creates the data structure your frontend needs
 */
function transformMetricsForDashboard(metrics) {
  // Sort by timestamp for time-series display
  const sortedMetrics = metrics.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  
  // Calculate summary statistics
  const successfulChecks = metrics.filter(m => m.success);
  const failedChecks = metrics.filter(m => !m.success);
  
  // Calculate uptime percentage
  const uptimePercentage = metrics.length > 0 
    ? (successfulChecks.length / metrics.length) * 100 
    : 0;
  
  // Calculate average latency for successful requests
  const avgLatency = successfulChecks.length > 0
    ? successfulChecks.reduce((sum, m) => sum + m.latencyMs, 0) / successfulChecks.length
    : 0;
  
  // Group by API for multi-API monitoring
  const apiGroups = {};
  sortedMetrics.forEach(metric => {
    const apiKey = metric.pk;
    if (!apiGroups[apiKey]) {
      apiGroups[apiKey] = {
        url: metric.url,
        dataPoints: [],
        currentStatus: 'unknown',
        stats: { uptime: 0, avgLatency: 0, totalChecks: 0 }
      };
    }
    
    apiGroups[apiKey].dataPoints.push({
      timestamp: metric.timestamp,
      latency: metric.latencyMs,
      statusCode: metric.statusCode,
      success: metric.success
    });
    
    // Update current status based on most recent check
    if (metric.timestamp === sortedMetrics[sortedMetrics.length - 1].timestamp) {
      apiGroups[apiKey].currentStatus = metric.success ? 'healthy' : 'unhealthy';
    }
  });
  
  // Calculate stats for each API
  Object.keys(apiGroups).forEach(apiKey => {
    const group = apiGroups[apiKey];
    const successful = group.dataPoints.filter(dp => dp.success);
    
    group.stats = {
      uptime: group.dataPoints.length > 0 ? (successful.length / group.dataPoints.length) * 100 : 0,
      avgLatency: successful.length > 0 ? successful.reduce((sum, dp) => sum + dp.latency, 0) / successful.length : 0,
      totalChecks: group.dataPoints.length
    };
  });
  
  return {
    // Overall system health
    summary: {
      uptime: Math.round(uptimePercentage * 100) / 100,
      averageLatency: Math.round(avgLatency * 100) / 100,
      totalChecks: metrics.length,
      failureCount: failedChecks.length,
      lastCheck: sortedMetrics.length > 0 ? sortedMetrics[sortedMetrics.length - 1].timestamp : null
    },
    
    // Time-series data for charts
    timeSeries: sortedMetrics.map(m => ({
      timestamp: m.timestamp,
      latency: m.latencyMs,
      status: m.success ? 'success' : 'failure',
      statusCode: m.statusCode
    })),
    
    // Per-API breakdown
    apis: apiGroups
  };
}