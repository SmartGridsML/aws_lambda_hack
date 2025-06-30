// src/healthCheck.js
const AWS = require('aws-sdk');
const https = require('https');
const { URL } = require('url');

// Initialize AWS services with best practices
const dynamodb = new AWS.DynamoDB.DocumentClient({
  // Use connection pooling for better performance
  httpOptions: {
    agent: new https.Agent({ keepAlive: true })
  }
});

/**
 * Health check handler with comprehensive monitoring
 * This function demonstrates several advanced patterns:
 * 1. Structured error handling for Lambda Destinations
 * 2. Performance measurement with high precision
 * 3. Standardized metrics collection
 * 4. Proper async/await error propagation
 */
exports.handler = async (event) => {
  console.log('Health check started:', JSON.stringify(event, null, 2));
  
  const { url, region } = event;
  const startTime = process.hrtime.bigint(); // High-precision timing
  
  try {
    // Perform the actual health check
    const result = await performHealthCheck(url);
    const endTime = process.hrtime.bigint();
    
    // Calculate latency in milliseconds with sub-millisecond precision
    const latencyMs = Number(endTime - startTime) / 1000000;
    
    // Create comprehensive metrics record
    const metrics = {
      pk: `api#${new URL(url).hostname}`, // Partition key for efficient querying
      timestamp: new Date().toISOString(),
      url: url,
      statusCode: result.statusCode,
      latencyMs: Math.round(latencyMs * 100) / 100, // Round to 2 decimal places
      region: region,
      success: result.statusCode >= 200 && result.statusCode < 300,
      // Add response size for bandwidth monitoring
      responseSize: result.responseSize || 0,
      // Track SSL certificate info for security monitoring
      sslInfo: result.sslInfo || null
    };
    
    // Store metrics in DynamoDB
    await dynamodb.put({
      TableName: process.env.METRICS_TABLE,
      Item: metrics
    }).promise();
    
    console.log('Health check completed successfully:', metrics);
    
    // Return success payload for Lambda Destinations
    return {
      statusCode: 200,
      body: {
        success: true,
        metrics: metrics,
        message: `API ${url} responded with ${result.statusCode} in ${latencyMs}ms`
      }
    };
    
  } catch (error) {
    console.error('Health check failed:', error);
    
    // Calculate failure latency
    const endTime = process.hrtime.bigint();
    const latencyMs = Number(endTime - startTime) / 1000000;
    
    // Store failure metrics - important for trend analysis
    const failureMetrics = {
      pk: `api#${new URL(url).hostname}`,
      timestamp: new Date().toISOString(),
      url: url,
      statusCode: 0, // Indicates connection failure
      latencyMs: latencyMs,
      region: region,
      success: false,
      errorType: error.code || 'UNKNOWN_ERROR',
      errorMessage: error.message
    };
    
    // Still record the failure in DynamoDB
    try {
      await dynamodb.put({
        TableName: process.env.METRICS_TABLE,
        Item: failureMetrics
      }).promise();
    } catch (dbError) {
      console.error('Failed to record failure metrics:', dbError);
    }
    
    // Throw error to trigger Lambda Destinations failure path
    throw new Error(`Health check failed for ${url}: ${error.message}`);
  }
};

/**
 * Performs HTTP health check with timeout and detailed response analysis
 */
async function performHealthCheck(url) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (parsedUrl.protocol === 'https:' ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method: 'GET',
      timeout: 5000, // 5 second timeout
      headers: {
        'User-Agent': 'AWS-Lambda-API-Monitor/1.0'
      }
    };
    
    const client = parsedUrl.protocol === 'https:' ? require('https') : require('http');
    
    const req = client.request(options, (res) => {
      let responseSize = 0;
      
      // Measure response size without storing full body
      res.on('data', (chunk) => {
        responseSize += chunk.length;
      });
      
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          responseSize: responseSize,
          sslInfo: res.socket?.authorized ? 'valid' : 'invalid'
        });
      });
    });
    
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    
    req.on('error', (error) => {
      reject(error);
    });
    
    req.end();
  });
}