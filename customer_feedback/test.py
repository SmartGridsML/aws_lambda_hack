# from main import RedditScraperDynamoDB

# def quick_test():
#     """Quick test of the scraper with minimal data"""
#     try:
#         scraper = RedditScraperDynamoDB()
        
#         # Test with just 3 posts, no comments
#         result = scraper.scrape_subreddit_comprehensive(
#             'test',  # Safe subreddit
#             limit=3,
#             include_comments=False
#         )
        
#         print(f"✅ Test successful: {result}")
#         return True
        
#     except Exception as e:
#         print(f"❌ Test failed: {e}")
#         return False

# if __name__ == "__main__":
#     quick_test()


# from lambda_func import lambda_handler

# # Test the Lambda function locally
# test_event = {
#     'processing_mode': 'batch',
#     'batch_size': 5
# }

# try:
#     result = lambda_handler(test_event, {})
#     print("✅ Lambda processing successful!")
#     print(result)
# except Exception as e:
#     print(f"❌ Lambda processing failed: {e}")

# from lambda_func import lambda_handler

# def test_sentiment_processing():
#     """Test sentiment analysis on your scraped Reddit data"""
    
#     print("🤖 Testing sentiment analysis processing...")
    
#     # Test with a small batch first
#     test_event = {
#         'processing_mode': 'batch',
#         'batch_size': 10  # Process 10 items
#     }
    
#     try:
#         result = lambda_handler(test_event, {})
#         print("✅ Sentiment processing successful!")
#         print(f"Result: {result}")
        
#         # Test with single post processing
#         print("\n🎯 Testing single post processing...")
#         single_test_event = {
#             'processing_mode': 'single',
#             'post_id': 'test_post_id'  # You can use a real post ID from your data
#         }
        
#         single_result = lambda_handler(single_test_event, {})
#         print(f"Single processing result: {single_result}")
        
#         return True
        
#     except Exception as e:
#         print(f"❌ Sentiment processing failed: {e}")
#         print(f"Error type: {type(e).__name__}")
#         return False

# if __name__ == "__main__":
#     test_sentiment_processing()

import requests
import subprocess
import time
import sys
import json
import os
import signal

def test_api_endpoints():
    """Test FastAPI endpoints with proper server startup"""
    
    print("🌐 Testing FastAPI backend...")
    
    api_process = None
    
    try:
        print("Starting FastAPI server...")
        
        # Start the server without reload for subprocess compatibility
        api_process = subprocess.Popen(
            [sys.executable, '-c', '''
import uvicorn
from fastapi_app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
            '''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # For proper process cleanup
        )
        
        # Wait longer for server to start
        print("Waiting for server to start...")
        time.sleep(8)
        
        # Check if process is still running
        if api_process.poll() is not None:
            stdout, stderr = api_process.communicate()
            print(f"❌ Server failed to start:")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            return False
        
        # Test endpoints with more detailed error handling
        endpoints = [
            ('http://localhost:8000/', 'Root Endpoint'),
            ('http://localhost:8000/health', 'Health Check'),
            ('http://localhost:8000/sentiments/summary', 'Sentiment Summary'),
            ('http://localhost:8000/sentiments?limit=5', 'Recent Sentiments'),
            ('http://localhost:8000/stats/processing', 'Processing Stats')
        ]
        
        all_passed = True
        
        for url, name in endpoints:
            try:
                print(f"\n📍 Testing: {name}")
                response = requests.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {name}: SUCCESS")
                    
                    # Show specific data for each endpoint
                    if 'summary' in url:
                        print(f"   📊 Total posts analyzed: {data.get('total_count', 0)}")
                        print(f"   📈 Positive: {data.get('positive_count', 0)}")
                        print(f"   📉 Negative: {data.get('negative_count', 0)}")
                        print(f"   ➖ Neutral: {data.get('neutral_count', 0)}")
                    
                    elif 'sentiments?' in url:
                        print(f"   📝 Retrieved {len(data)} sentiment records")
                        if data:
                            print(f"   🔍 Latest sentiment: {data[0].get('sentiment', 'N/A')}")
                    
                    elif 'processing' in url:
                        print(f"   🔄 Raw posts: {data.get('raw_posts_count', 0)}")
                        print(f"   ✅ Processed: {data.get('processed_posts_count', 0)}")
                        print(f"   📊 Processing rate: {data.get('processing_rate_percent', 0)}%")
                    
                    elif 'health' in url:
                        print(f"   🏥 Status: {data.get('status', 'unknown')}")
                        print(f"   🗄️ DynamoDB: {data.get('services', {}).get('dynamodb', 'unknown')}")
                
                else:
                    print(f"❌ {name}: HTTP {response.status_code}")
                    print(f"   Response: {response.text}")
                    all_passed = False
                    
            except requests.exceptions.ConnectionError as e:
                print(f"❌ {name}: Connection failed - {e}")
                all_passed = False
            except requests.exceptions.Timeout as e:
                print(f"❌ {name}: Timeout - {e}")
                all_passed = False
            except Exception as e:
                print(f"❌ {name}: {e}")
                all_passed = False
        
        # Results summary
        print("\n" + "="*50)
        print("🎯 API TEST RESULTS")
        print("="*50)
        
        if all_passed:
            print("🎉 ALL ENDPOINTS WORKING!")
            print("\n🚀 Your Reddit Sentiment Analysis API is ready!")
            print("📊 Dashboard: Open frontend/index.html in your browser")
            print("📚 API Docs: http://localhost:8000/docs")
            
            # Offer to keep server running
            print("\n❓ Keep API server running for dashboard testing? (y/n): ", end="")
            try:
                choice = input().lower().strip()
                if choice == 'y' or choice == 'yes':
                    print("🖥️ API server is running at http://localhost:8000")
                    print("📱 Open frontend/index.html in your browser")
                    print("Press Ctrl+C to stop the server")
                    
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        print("\n👋 Stopping API server...")
            except:
                pass
        else:
            print("⚠️ Some endpoints failed. Check the errors above.")
        
        return all_passed
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False
    
    finally:
        # Clean up the server process
        if api_process:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(api_process.pid), signal.SIGTERM)
                else:
                    api_process.terminate()
                
                # Wait for process to terminate
                try:
                    api_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(api_process.pid), signal.SIGKILL)
                    else:
                        api_process.kill()
                
                print("🛑 API server stopped")
            except Exception as cleanup_error:
                print(f"⚠️ Error stopping server: {cleanup_error}")

def test_quick_server():
    """Quick test to just verify the server can start"""
    print("🔧 Quick server startup test...")
    
    try:
        # Test import
        from fastapi_app import app
        print("✅ FastAPI app imports successfully")
        
        # Test DynamoDB connection
        import boto3
        from dotenv import load_dotenv
        load_dotenv()
        
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        raw_table = dynamodb.Table('reddit-raw-posts')
        processed_table = dynamodb.Table('reddit-processed-sentiment')
        
        # Quick connection test
        raw_table.scan(Limit=1)
        processed_table.scan(Limit=1)
        print("✅ DynamoDB connection working")
        
        return True
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        return False

if __name__ == "__main__":
    # Run quick test first
    if test_quick_server():
        print("\n" + "="*50)
        test_api_endpoints()
    else:
        print("❌ Basic components failed. Fix the issues above before running the full test.")