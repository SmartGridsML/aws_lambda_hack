// src/alert.js
const AWS = require('aws-sdk');
const sns = new AWS.SNS();

/**
 * Processes failed health checks and sends enriched alerts
 * This demonstrates advanced event processing patterns
 */
exports.handler = async (event) => {
  console.log('Processing alert event:', JSON.stringify(event, null, 2));
  
  try {
    // Process each SQS message (failed health check)
    for (const record of event.Records) {
      const failureData = JSON.parse(record.body);
      await processFailureAlert(failureData);
    }
    
    return { statusCode: 200, body: 'Alerts processed successfully' };
    
  } catch (error) {
    console.error('Alert processing failed:', error);
    throw error; // This will cause SQS to retry
  }
};

async function processFailureAlert(failureData) {
  // Create enriched alert message
  const alertMessage = {
    severity: 'HIGH',
    timestamp: new Date().toISOString(),
    api: failureData.url || 'Unknown API',
    error: failureData.errorMessage || 'Health check failed',
    region: failureData.region || 'us-east-1',
    // Add runbook links for quick resolution
    runbook: `https://wiki.company.com/runbooks/api-failure`,
    dashboard: process.env.DASHBOARD_URL
  };
  
  console.log('Sending alert:', alertMessage);
  
  // Send to SNS for multiple notification channels
  await sns.publish({
    TopicArn: process.env.ALERT_TOPIC,
    Subject: `🚨 API Health Check Failed: ${alertMessage.api}`,
    Message: JSON.stringify(alertMessage, null, 2)
  }).promise();
}