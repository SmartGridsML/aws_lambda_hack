import json
import boto3
from datetime import datetime
from decimal import Decimal
import os
from typing import Dict, Any

# Initialize clients
dynamodb = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')
processed_table = dynamodb.Table(os.getenv('PROCESSED_DATA_TABLE', 'reddit-processed-sentiment'))

def dynamodb_stream_handler(event, context):
    """
    Real-time DynamoDB Stream handler for processing new Reddit posts
    Triggered automatically when new posts are added to raw-posts table
    """
    print(f"🔄 Processing {len(event['Records'])} DynamoDB stream records")
    
    processed_count = 0
    errors = []
    
    for record in event['Records']:
        try:
            # Only process INSERT events (new posts)
            if record['eventName'] == 'INSERT':
                new_image = record['dynamodb']['NewImage']
                
                # Process the new post immediately
                result = process_single_post_realtime(new_image)
                
                if result:
                    processed_count += 1
                    print(f"✅ Processed post: {result['analysis_id']}")
                    
                    # Optional: Send real-time notification
                    await_notification(result)
                
        except Exception as e:
            error_msg = f"Error processing record: {str(e)}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
    
    # Return processing summary
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_count': processed_count,
            'errors': errors,
            'timestamp': datetime.now().isoformat()
        })
    }

def process_single_post_realtime(dynamodb_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single Reddit post in real-time using Amazon Comprehend
    """
    try:
        # Extract data from DynamoDB item format
        post_id = dynamodb_item['post_id']['S']
        title = dynamodb_item.get('title', {}).get('S', '')
        content = dynamodb_item.get('content', {}).get('S', '')
        subreddit = dynamodb_item.get('subreddit', {}).get('S', 'unknown')
        
        # Combine title and content for analysis
        text_to_analyze = f"{title} {content}".strip()
        
        if not text_to_analyze:
            print(f"⚠️ No text content for post {post_id}")
            return None
        
        # Truncate if too long (Comprehend limit is 5000 bytes)
        if len(text_to_analyze.encode('utf-8')) > 5000:
            text_to_analyze = text_to_analyze[:4900] + "..."
        
        # Call Amazon Comprehend for sentiment analysis
        sentiment_response = comprehend.detect_sentiment(
            Text=text_to_analyze,
            LanguageCode='en'
        )
        
        # Extract sentiment results
        sentiment = sentiment_response['Sentiment']
        confidence_scores = sentiment_response['SentimentScore']
        
        # Get the confidence for the detected sentiment
        confidence_map = {
            'POSITIVE': confidence_scores['Positive'],
            'NEGATIVE': confidence_scores['Negative'],
            'NEUTRAL': confidence_scores['Neutral'],
            'MIXED': confidence_scores['Mixed']
        }
        confidence = confidence_map[sentiment]
        
        # Detect keywords (simple approach)
        keywords = detect_business_keywords(text_to_analyze)
        
        # Create analysis record
        analysis_id = f"rt_{post_id}_{int(datetime.now().timestamp())}"
        
        analysis_record = {
            'analysis_id': analysis_id,
            'original_post_id': post_id,
            'input_text': text_to_analyze,
            'sentiment': sentiment,
            'confidence_score': Decimal(str(round(confidence, 4))),
            'sentiment_scores': {
                'positive': Decimal(str(round(confidence_scores['Positive'], 4))),
                'negative': Decimal(str(round(confidence_scores['Negative'], 4))),
                'neutral': Decimal(str(round(confidence_scores['Neutral'], 4))),
                'mixed': Decimal(str(round(confidence_scores['Mixed'], 4)))
            },
            'keywords_detected': keywords,
            'subreddit': subreddit,
            'processed_timestamp': Decimal(str(datetime.now().timestamp())),
            'processing_method': 'realtime_stream',
            'analysis_metadata': {
                'comprehend_version': 'real-time',
                'processing_latency_ms': 0  # Would need timing logic
            }
        }
        
        # Save to processed table
        processed_table.put_item(Item=analysis_record)
        
        print(f"🎯 Real-time analysis complete: {sentiment} ({confidence:.3f})")
        
        return analysis_record
        
    except Exception as e:
        print(f"❌ Error in real-time processing: {e}")
        raise

def detect_business_keywords(text: str) -> list:
    """Detect business-relevant keywords in text"""
    business_keywords = [
        'aws', 'lambda', 'serverless', 'api gateway', 'dynamodb',
        'microservices', 'cloud', 'docker', 'kubernetes', 'devops',
        'pricing', 'cost', 'performance', 'scalability', 'architecture'
    ]
    
    text_lower = text.lower()
    detected = [kw for kw in business_keywords if kw in text_lower]
    
    return detected

async def send_notification(analysis_result: Dict[str, Any]):
    """
    Send real-time notification about new sentiment analysis
    Could be WebSocket, SNS, SES, etc.
    """
    try:
        # Example: Send to SNS topic for real-time alerts
        sns = boto3.client('sns')
        
        # Only send notifications for strong positive/negative sentiment
        confidence = float(analysis_result['confidence_score'])
        sentiment = analysis_result['sentiment']
        
        if confidence > 0.8 and sentiment in ['POSITIVE', 'NEGATIVE']:
            message = {
                'alert_type': 'high_confidence_sentiment',
                'sentiment': sentiment,
                'confidence': confidence,
                'subreddit': analysis_result['subreddit'],
                'keywords': analysis_result['keywords_detected'],
                'timestamp': analysis_result['processed_timestamp']
            }
            
            # Send to SNS (configure topic ARN in environment)
            topic_arn = os.getenv('SNS_TOPIC_ARN')
            if topic_arn:
                sns.publish(
                    TopicArn=topic_arn,
                    Subject=f"High Confidence {sentiment} Sentiment Detected",
                    Message=json.dumps(message, indent=2)
                )
                
                print(f"📨 Notification sent for {sentiment} sentiment")
    
    except Exception as e:
        print(f"⚠️ Notification failed: {e}")

# =====================================
# LAMBDA HANDLER FOR STREAMS
# =====================================

def lambda_handler(event, context):
    """Main Lambda handler for DynamoDB streams"""
    return dynamodb_stream_handler(event, context)