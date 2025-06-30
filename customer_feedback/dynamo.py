import boto3
import json
from datetime import datetime

def create_dynamodb_tables():
    """
    Create the DynamoDB tables needed for our Reddit sentiment analysis system.
    
    This function demonstrates several important DynamoDB concepts:
    1. Partition keys and sort keys for efficient querying
    2. Global Secondary Indexes (GSI) for different access patterns
    3. Billing modes and capacity planning
    4. Table configuration for different use cases
    
    Think of this as building the foundation of your data warehouse - 
    getting this structure right is crucial for performance and costs.
    """
    
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')
    
    # Table 1: Raw Reddit Data Storage
    # This table stores all the raw posts and comments we scrape from Reddit
    raw_posts_table = {
        'TableName': 'reddit-raw-posts',
        'KeySchema': [
            {
                'AttributeName': 'post_id',  # Partition Key - distributes data across partitions
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'created_timestamp',  # Sort Key - enables time-based queries
                'KeyType': 'RANGE'
            }
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'post_id',
                'AttributeType': 'S'  # String
            },
            {
                'AttributeName': 'created_timestamp',
                'AttributeType': 'N'  # Number (Unix timestamp)
            },
            {
                'AttributeName': 'subreddit',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'processing_status',
                'AttributeType': 'S'
            }
        ],
        'GlobalSecondaryIndexes': [
            {
                # GSI 1: Query by subreddit and time
                # This allows us to efficiently find all posts from a specific subreddit
                'IndexName': 'subreddit-timestamp-index',
                'KeySchema': [
                    {
                        'AttributeName': 'subreddit',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'created_timestamp',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'  # Include all attributes in the index
                }
                # Note: GSI inherits billing mode from the main table
            },
            {
                # GSI 2: Query by processing status
                # This helps us find posts that need processing or have been processed
                'IndexName': 'processing-status-index',
                'KeySchema': [
                    {
                        'AttributeName': 'processing_status',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'created_timestamp',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
                # Note: GSI inherits billing mode from the main table
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST',  # Pay only for what you use - great for variable workloads
        'Tags': [
            {
                'Key': 'Project',
                'Value': 'RedditSentimentAnalysis'
            },
            {
                'Key': 'Environment',
                'Value': 'Development'
            }
        ]
    }
    
    # Table 2: Processed Sentiment Data
    # This table stores the results of our sentiment analysis processing
    processed_sentiment_table = {
        'TableName': 'reddit-processed-sentiment',
        'KeySchema': [
            {
                'AttributeName': 'analysis_id',  # Unique identifier for each analysis
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'processed_timestamp',  # When the analysis was completed
                'KeyType': 'RANGE'
            }
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'analysis_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'processed_timestamp',
                'AttributeType': 'N'
            },
            {
                'AttributeName': 'sentiment',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'subreddit',
                'AttributeType': 'S'
            }
        ],
        'GlobalSecondaryIndexes': [
            {
                # GSI 1: Query by sentiment type
                # This allows us to quickly find all positive, negative, or neutral posts
                'IndexName': 'sentiment-timestamp-index',
                'KeySchema': [
                    {
                        'AttributeName': 'sentiment',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'processed_timestamp',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
                # Note: GSI inherits billing mode from the main table
            },
            {
                # GSI 2: Query by subreddit for community-specific analysis
                'IndexName': 'subreddit-sentiment-index',
                'KeySchema': [
                    {
                        'AttributeName': 'subreddit',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'processed_timestamp',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
                # Note: GSI inherits billing mode from the main table
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST',
        'Tags': [
            {
                'Key': 'Project',
                'Value': 'RedditSentimentAnalysis'
            },
            {
                'Key': 'Environment',
                'Value': 'Development'
            }
        ]
    }
    
    # Create the tables
    tables_to_create = [
        ('reddit-raw-posts', raw_posts_table),
        ('reddit-processed-sentiment', processed_sentiment_table)
    ]
    
    for table_name, table_config in tables_to_create:
        try:
            print(f"Creating table: {table_name}")
            
            # Check if table already exists
            try:
                response = dynamodb.describe_table(TableName=table_name)
                print(f"✅ Table {table_name} already exists")
                continue
            except dynamodb.exceptions.ResourceNotFoundException:
                # Table doesn't exist, so we can create it
                pass
            
            # Create the table
            response = dynamodb.create_table(**table_config)
            print(f"✅ Table {table_name} creation initiated")
            print(f"   ARN: {response['TableDescription']['TableArn']}")
            
            # Wait for table to be active
            print(f"⏳ Waiting for table {table_name} to become active...")
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            print(f"✅ Table {table_name} is now active and ready for use!")
            
        except Exception as e:
            print(f"❌ Error creating table {table_name}: {e}")

def create_sample_data_for_testing():
    """
    Create some sample data in our tables for testing purposes.
    
    This function demonstrates the data structure and helps you understand
    how the sentiment analysis pipeline will work with real data.
    """
    
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    
    # Check if tables exist before trying to insert data
    try:
        raw_posts_table = dynamodb.Table('reddit-raw-posts')
        processed_table = dynamodb.Table('reddit-processed-sentiment')
        
        # Verify tables exist
        raw_posts_table.load()
        processed_table.load()
        
    except Exception as e:
        print(f"❌ Cannot access tables for sample data: {e}")
        print("Make sure the tables were created successfully first.")
        return
    
    from decimal import Decimal
    import uuid
    
    # Sample raw posts (these would normally come from your scraper)
    sample_posts = [
        {
            'post_id': 'sample_post_1',
            'created_timestamp': Decimal(str(datetime.now().timestamp())),
            'title': 'AWS Lambda is amazing for serverless computing',
            'selftext': 'I just built my first serverless application and the performance is incredible!',
            'combined_text': 'AWS Lambda is amazing for serverless computing I just built my first serverless application and the performance is incredible!',
            'subreddit': 'aws',
            'author': 'developer123',
            'score': 45,
            'num_comments': 8,
            'item_type': 'post',
            'processing_status': 'raw',
            'scraped_at': Decimal(str(datetime.now().timestamp()))
        },
        {
            'post_id': 'sample_post_2',
            'created_timestamp': Decimal(str(datetime.now().timestamp() - 3600)),
            'title': 'Having issues with Lambda cold starts',
            'selftext': 'My Lambda functions are taking too long to start. Very frustrating for user experience.',
            'combined_text': 'Having issues with Lambda cold starts My Lambda functions are taking too long to start. Very frustrating for user experience.',
            'subreddit': 'serverless',
            'author': 'frustrated_dev',
            'score': 23,
            'num_comments': 15,
            'item_type': 'post',
            'processing_status': 'raw',
            'scraped_at': Decimal(str(datetime.now().timestamp()))
        },
        {
            'post_id': 'sample_post_3',
            'created_timestamp': Decimal(str(datetime.now().timestamp() - 7200)),
            'title': 'Neutral post about cloud computing trends',
            'selftext': 'Here are some statistics about cloud adoption in 2024. The data shows steady growth.',
            'combined_text': 'Neutral post about cloud computing trends Here are some statistics about cloud adoption in 2024. The data shows steady growth.',
            'subreddit': 'programming',
            'author': 'analyst_user',
            'score': 67,
            'num_comments': 5,
            'item_type': 'post',
            'processing_status': 'raw',
            'scraped_at': Decimal(str(datetime.now().timestamp()))
        }
    ]
    
    # Sample processed sentiment data (these would be created by your Lambda function)
    sample_processed_data = [
        {
            'analysis_id': str(uuid.uuid4()),
            'processed_timestamp': Decimal(str(datetime.now().timestamp())),
            'original_post_id': 'sample_post_1',
            'input_text': 'AWS Lambda is amazing for serverless computing I just built my first serverless application and the performance is incredible!',
            'sentiment': 'POSITIVE',
            'confidence_score': Decimal('0.95'),
            'subreddit': 'aws',
            'keywords_detected': ['AWS Lambda', 'serverless', 'performance'],
            'analysis_metadata': {
                'processing_time_ms': 234,
                'model_version': '1.0',
                'language_detected': 'en'
            }
        },
        {
            'analysis_id': str(uuid.uuid4()),
            'processed_timestamp': Decimal(str(datetime.now().timestamp() - 1800)),
            'original_post_id': 'sample_post_2',
            'input_text': 'Having issues with Lambda cold starts My Lambda functions are taking too long to start. Very frustrating for user experience.',
            'sentiment': 'NEGATIVE',
            'confidence_score': Decimal('0.89'),
            'subreddit': 'serverless',
            'keywords_detected': ['Lambda', 'cold starts', 'frustrating'],
            'analysis_metadata': {
                'processing_time_ms': 187,
                'model_version': '1.0',
                'language_detected': 'en'
            }
        },
        {
            'analysis_id': str(uuid.uuid4()),
            'processed_timestamp': Decimal(str(datetime.now().timestamp() - 3600)),
            'original_post_id': 'sample_post_3',
            'input_text': 'Neutral post about cloud computing trends Here are some statistics about cloud adoption in 2024. The data shows steady growth.',
            'sentiment': 'NEUTRAL',
            'confidence_score': Decimal('0.76'),
            'subreddit': 'programming',
            'keywords_detected': ['cloud computing', 'data', 'growth'],
            'analysis_metadata': {
                'processing_time_ms': 156,
                'model_version': '1.0',
                'language_detected': 'en'
            }
        }
    ]
    
    # Insert sample data
    print("Creating sample data for testing...")
    
    try:
        # Insert raw posts
        with raw_posts_table.batch_writer() as batch:
            for post in sample_posts:
                batch.put_item(Item=post)
        print(f"✅ Inserted {len(sample_posts)} sample posts")
        
        # Insert processed sentiment data
        with processed_table.batch_writer() as batch:
            for processed_item in sample_processed_data:
                batch.put_item(Item=processed_item)
        print(f"✅ Inserted {len(sample_processed_data)} sample processed items")
        
        print("🎉 Sample data created successfully!")
        print("Your tables now have test data for development and testing.")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")

def main():
    """
    Set up the complete DynamoDB infrastructure for the sentiment analysis system.
    """
    
    print("🚀 Setting up DynamoDB infrastructure for Reddit Sentiment Analysis")
    print("=" * 70)
    
    # Step 1: Create tables
    print("\nStep 1: Creating DynamoDB tables...")
    create_dynamodb_tables()
    
    # Step 2: Create sample data for testing
    print("\nStep 2: Creating sample data for testing...")
    create_sample_data_for_testing()
    
    print("\n" + "=" * 70)
    print("✅ DynamoDB setup complete!")
    print("\nYour database is now ready with:")
    print("📊 reddit-raw-posts table - for storing scraped Reddit data")
    print("🤖 reddit-processed-sentiment table - for storing analysis results")
    print("🧪 Sample test data in both tables")
   
if __name__ == "__main__":
    main()