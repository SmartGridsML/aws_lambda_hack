import json
import boto3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any
import re

# Lambda function for processing Reddit sentiment analysis
# This function demonstrates several serverless best practices:
# 1. Efficient batch processing of data
# 2. Integration with multiple AWS services
# 3. Error handling and logging for production systems
# 4. Cost-effective sentiment analysis without external APIs

class SentimentAnalyzer:
    """
    A lightweight sentiment analyzer that works within Lambda constraints.
    
    This class demonstrates how to build a practical sentiment analysis system
    without relying on external APIs, which helps control costs and latency.
    For production systems, you might integrate with AWS Comprehend or other
    more sophisticated NLP services, but this approach gives you full control.
    """
    
    def __init__(self):
        # Define sentiment keywords and their weights
        # This approach is simple but surprisingly effective for business monitoring
        self.positive_keywords = {
            'love', 'amazing', 'fantastic', 'excellent', 'great', 'awesome', 
            'perfect', 'wonderful', 'brilliant', 'outstanding', 'impressive',
            'helpful', 'useful', 'easy', 'simple', 'fast', 'reliable',
            'recommend', 'best', 'good', 'nice', 'cool', 'solid'
        }
        
        self.negative_keywords = {
            'hate', 'terrible', 'awful', 'horrible', 'bad', 'worst',
            'frustrated', 'annoying', 'broken', 'useless', 'slow',
            'expensive', 'confusing', 'difficult', 'problems', 'issues',
            'bug', 'error', 'fail', 'crashed', 'disappointing', 'waste'
        }
        
        # Intensity multipliers for stronger sentiment expressions
        self.intensifiers = {
            'very': 1.5, 'extremely': 2.0, 'incredibly': 2.0,
            'absolutely': 1.8, 'completely': 1.6, 'totally': 1.6
        }
    
    def preprocess_text(self, text: str) -> str:
        """
        Clean and prepare text for sentiment analysis.
        
        This function demonstrates text preprocessing techniques that improve
        the accuracy of sentiment analysis by normalizing the input.
        """
        if not text:
            return ""
        
        # Convert to lowercase for consistent matching
        text = text.lower()
        
        # Remove URLs, which often add noise to sentiment analysis
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove Reddit-specific formatting
        text = re.sub(r'/u/\w+', '', text)  # Remove username mentions
        text = re.sub(r'/r/\w+', '', text)  # Remove subreddit mentions
        text = re.sub(r'\*\*.*?\*\*', '', text)  # Remove bold text markers
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        return text
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze the sentiment of given text and return detailed results.
        
        This function returns not just a sentiment label, but also confidence
        scores and the specific words that influenced the decision. This
        transparency helps you understand and trust the analysis results.
        """
        
        if not text:
            return {
                'sentiment': 'NEUTRAL',
                'confidence': 0.0,
                'positive_score': 0.0,
                'negative_score': 0.0,
                'detected_keywords': []
            }
        
        # Preprocess the text
        clean_text = self.preprocess_text(text)
        words = clean_text.split()
        
        positive_score = 0.0
        negative_score = 0.0
        detected_keywords = []
        
        # Analyze each word and its context
        for i, word in enumerate(words):
            base_weight = 1.0
            
            # Check for intensifiers in the previous word
            if i > 0 and words[i-1] in self.intensifiers:
                base_weight = self.intensifiers[words[i-1]]
            
            # Calculate sentiment contributions
            if word in self.positive_keywords:
                positive_score += base_weight
                detected_keywords.append(f"+{word}")
            elif word in self.negative_keywords:
                negative_score += base_weight
                detected_keywords.append(f"-{word}")
        
        # Determine overall sentiment
        total_score = positive_score - negative_score
        
        if total_score > 1.0:
            sentiment = 'POSITIVE'
            confidence = min(0.95, 0.5 + (total_score / 10))
        elif total_score < -1.0:
            sentiment = 'NEGATIVE'
            confidence = min(0.95, 0.5 + (abs(total_score) / 10))
        elif positive_score > 0 and negative_score > 0:
            sentiment = 'MIXED'
            confidence = 0.6 + (min(positive_score, negative_score) / 10)
        else:
            sentiment = 'NEUTRAL'
            confidence = 0.5 + (len(words) / 200)  # Longer neutral text = higher confidence
        
        return {
            'sentiment': sentiment,
            'confidence': round(confidence, 3),
            'positive_score': round(positive_score, 2),
            'negative_score': round(negative_score, 2),
            'detected_keywords': detected_keywords[:10]  # Limit for storage efficiency
        }
    
    def extract_business_keywords(self, text: str) -> List[str]:
        """
        Extract business-relevant keywords from the text.
        
        This function identifies specific terms that might be important for
        your business intelligence, helping you track mentions of products,
        competitors, or key concepts.
        """
        
        # Define business-relevant keyword patterns
        business_patterns = {
            'aws_services': r'\b(lambda|api gateway|dynamodb|s3|ec2|rds|cloudfront|sqs|sns)\b',
            'competitors': r'\b(azure|google cloud|gcp|heroku|digital ocean|vercel)\b',
            'technologies': r'\b(serverless|microservices|docker|kubernetes|terraform)\b',
            'sentiment_context': r'\b(pricing|cost|performance|speed|reliability|support)\b'
        }
        
        detected_keywords = []
        text_lower = text.lower()
        
        for category, pattern in business_patterns.items():
            matches = re.findall(pattern, text_lower)
            for match in matches:
                detected_keywords.append(f"{category}:{match}")
        
        return detected_keywords[:15]  # Limit for storage efficiency


def lambda_handler(event, context):
    """
    Main Lambda function handler for processing Reddit sentiment analysis.
    
    This function is triggered by various events (scheduled runs, API calls, or
    database changes) and processes raw Reddit data to extract sentiment insights.
    
    The function demonstrates several Lambda best practices:
    1. Efficient batch processing to maximize cost-effectiveness
    2. Proper error handling and logging
    3. Integration with multiple AWS services
    4. Structured response formatting
    """
    
    print(f"Starting sentiment analysis processing at {datetime.now()}")
    
    # Initialize AWS services
    dynamodb = boto3.resource('dynamodb')
    raw_posts_table = dynamodb.Table('reddit-raw-posts')
    processed_table = dynamodb.Table('reddit-processed-sentiment')
    
    # Initialize sentiment analyzer
    analyzer = SentimentAnalyzer()
    
    # Determine processing mode based on event type
    processing_mode = event.get('processing_mode', 'batch')
    batch_size = event.get('batch_size', 25)  # Process 25 items at a time
    
    try:
        if processing_mode == 'single':
            # Process a specific post (useful for real-time processing)
            result = process_single_post(event, analyzer, raw_posts_table, processed_table)
        else:
            # Process a batch of unprocessed posts (useful for scheduled runs)
            result = process_batch_posts(analyzer, raw_posts_table, processed_table, batch_size)
        
        print(f"Processing completed successfully: {result}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Sentiment analysis completed successfully',
                'results': result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error during sentiment processing: {str(e)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Sentiment analysis failed',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }


def process_single_post(event, analyzer, raw_table, processed_table):
    """
    Process sentiment analysis for a single post.
    
    This function handles real-time processing scenarios where you want to
    analyze sentiment immediately after scraping new content.
    """
    
    post_id = event.get('post_id')
    if not post_id:
        raise ValueError("post_id is required for single post processing")
    
    # Fetch the post from DynamoDB
    response = raw_table.query(
        KeyConditionExpression='post_id = :post_id',
        ExpressionAttributeValues={':post_id': post_id}
    )
    
    if not response['Items']:
        raise ValueError(f"Post {post_id} not found in raw posts table")
    
    post = response['Items'][0]
    
    # Process the sentiment
    result = process_post_sentiment(post, analyzer, processed_table)
    
    # Update the raw post's processing status
    raw_table.update_item(
        Key={
            'post_id': post['post_id'],
            'created_timestamp': post['created_timestamp']
        },
        UpdateExpression='SET processing_status = :status',
        ExpressionAttributeValues={':status': 'processed'}
    )
    
    return {
        'processed_posts': 1,
        'analysis_id': result['analysis_id']
    }


def process_batch_posts(analyzer, raw_table, processed_table, batch_size):
    """
    Process sentiment analysis for a batch of unprocessed posts.
    
    This function demonstrates efficient batch processing, which is more
    cost-effective for Lambda than processing items one at a time.
    """
    
    print(f"Starting batch processing for up to {batch_size} posts")
    
    # Find unprocessed posts using the Global Secondary Index
    response = raw_table.query(
        IndexName='processing-status-index',
        KeyConditionExpression='processing_status = :status',
        ExpressionAttributeValues={':status': 'raw'},
        Limit=batch_size
    )
    
    unprocessed_posts = response['Items']
    print(f"Found {len(unprocessed_posts)} unprocessed posts")
    
    if not unprocessed_posts:
        return {
            'processed_posts': 0,
            'message': 'No unprocessed posts found'
        }
    
    processed_count = 0
    analysis_ids = []
    
    # Process each post
    for post in unprocessed_posts:
        try:
            # Perform sentiment analysis
            result = process_post_sentiment(post, analyzer, processed_table)
            analysis_ids.append(result['analysis_id'])
            
            # Update the processing status in the raw posts table
            raw_table.update_item(
                Key={
                    'post_id': post['post_id'],
                    'created_timestamp': post['created_timestamp']
                },
                UpdateExpression='SET processing_status = :status, processed_at = :timestamp',
                ExpressionAttributeValues={
                    ':status': 'processed',
                    ':timestamp': Decimal(str(datetime.now(timezone.utc).timestamp()))
                }
            )
            
            processed_count += 1
            
        except Exception as e:
            print(f"Error processing post {post.get('post_id', 'unknown')}: {e}")
            
            # Mark as error for later investigation
            raw_table.update_item(
                Key={
                    'post_id': post['post_id'],
                    'created_timestamp': post['created_timestamp']
                },
                UpdateExpression='SET processing_status = :status, error_message = :error',
                ExpressionAttributeValues={
                    ':status': 'error',
                    ':error': str(e)
                }
            )
    
    return {
        'processed_posts': processed_count,
        'analysis_ids': analysis_ids,
        'total_found': len(unprocessed_posts)
    }


def process_post_sentiment(post, analyzer, processed_table):
    """
    Process sentiment analysis for a single post and save results.
    
    This function encapsulates the core sentiment analysis logic and
    demonstrates how to structure the results for storage and later retrieval.
    """
    
    # Extract text for analysis
    combined_text = post.get('combined_text', '')
    if not combined_text:
        # Fallback to title + selftext if combined_text not available
        title = post.get('title', '')
        selftext = post.get('selftext', '')
        combined_text = f"{title} {selftext}".strip()
    
    # Perform sentiment analysis
    sentiment_result = analyzer.analyze_sentiment(combined_text)
    
    # Extract business keywords
    business_keywords = analyzer.extract_business_keywords(combined_text)
    
    # Create analysis record
    analysis_id = str(uuid.uuid4())
    current_timestamp = datetime.now(timezone.utc).timestamp()
    
    analysis_record = {
        'analysis_id': analysis_id,
        'processed_timestamp': Decimal(str(current_timestamp)),
        'original_post_id': post['post_id'],
        'input_text': combined_text[:1000],  # Truncate very long texts for storage efficiency
        'sentiment': sentiment_result['sentiment'],
        'confidence_score': Decimal(str(sentiment_result['confidence'])),
        'positive_score': Decimal(str(sentiment_result['positive_score'])),
        'negative_score': Decimal(str(sentiment_result['negative_score'])),
        'detected_keywords': sentiment_result['detected_keywords'],
        'business_keywords': business_keywords,
        'subreddit': post.get('subreddit', 'unknown'),
        'original_author': post.get('author', 'unknown'),
        'original_score': post.get('score', 0),
        'original_created_timestamp': post.get('created_timestamp', Decimal('0')),
        'analysis_metadata': {
            'processing_time_ms': 0,  # Could add timing if needed
            'model_version': '1.0',
            'language_detected': 'en'  # Could add language detection
        }
    }
    
    # Save to processed sentiment table
    processed_table.put_item(Item=analysis_record)
    
    print(f"Processed sentiment for post {post['post_id']}: {sentiment_result['sentiment']} (confidence: {sentiment_result['confidence']})")
    
    return {
        'analysis_id': analysis_id,
        'sentiment': sentiment_result['sentiment'],
        'confidence': sentiment_result['confidence']
    }


# For testing the Lambda function locally
if __name__ == "__main__":
    # Test event for local development
    test_event = {
        'processing_mode': 'batch',
        'batch_size': 10
    }
    
    test_context = {}
    
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))