from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime
import os
from dotenv import load_dotenv
from decimal import Decimal
import json
from typing import Optional, List, Dict, Any
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel

# Add Mangum for Lambda compatibility
try:
    from mangum import Mangum
    LAMBDA_AVAILABLE = True
except ImportError:
    LAMBDA_AVAILABLE = False
    print("⚠️ Mangum not installed. Lambda handler disabled.")

# Load environment variables (for local development)
if os.path.exists('.env'):
    load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Reddit Sentiment Analysis API",
    description="API for serving Reddit sentiment analysis data from DynamoDB",
    version="1.0.0",
    # Add root_path for Lambda deployment
    root_path=os.getenv("ROOT_PATH", "")
)

# Enhanced CORS configuration for both local and Lambda deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "file://",  # Allow file:// protocol for local HTML files
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Initialize DynamoDB with better error handling for Lambda
def get_dynamodb_tables():
    """Initialize DynamoDB tables with fallback for different environments"""
    try:
        # Use environment variables or defaults
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        # For Lambda, boto3 will automatically use the execution role
        # For local development, it will use credentials from .env or AWS CLI
        dynamodb = boto3.resource('dynamodb', region_name=region)
        
        raw_posts_table = dynamodb.Table(os.getenv('RAW_POSTS_TABLE', 'reddit-raw-posts'))
        processed_table = dynamodb.Table(os.getenv('PROCESSED_DATA_TABLE', 'reddit-processed-sentiment'))
        
        # Test connection
        raw_posts_table.scan(Limit=1)
        processed_table.scan(Limit=1)
        
        print("✅ Connected to DynamoDB tables")
        return raw_posts_table, processed_table
        
    except Exception as e:
        print(f"❌ Failed to connect to DynamoDB: {e}")
        return None, None

# Initialize tables
raw_posts_table, processed_table = get_dynamodb_tables()

def decimal_to_float(obj):
    """Convert DynamoDB Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(v) for v in obj]
    return obj

def format_timestamp(timestamp):
    """Convert timestamp to ISO format string"""
    try:
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp).isoformat()
        elif isinstance(timestamp, Decimal):
            return datetime.fromtimestamp(float(timestamp)).isoformat()
        elif isinstance(timestamp, str):
            return timestamp
        else:
            return datetime.now().isoformat()
    except:
        return datetime.now().isoformat()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Reddit Sentiment Analysis API",
        "version": "1.0.0",
        "status": "operational",
        "environment": "lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "local",
        "endpoints": {
            "sentiments": "/sentiments",
            "summary": "/sentiments/summary",
            "stats": "/stats/processing",
            "health": "/health",
            "status": "/status",
            "docs": "/docs"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
async def status():
    """Simple status endpoint for Lambda health checks"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "environment": "lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "local",
        "database_connected": raw_posts_table is not None and processed_table is not None
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        if not raw_posts_table or not processed_table:
            raise Exception("DynamoDB tables not initialized")
            
        # Test DynamoDB connection
        raw_posts_table.scan(Limit=1)
        processed_table.scan(Limit=1)
        
        return {
            "status": "healthy",
            "services": {
                "dynamodb": "connected",
                "api": "operational"
            },
            "environment": "lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "local",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/sentiments")
async def get_sentiments(
    limit: int = Query(50, ge=1, le=100, description="Number of sentiment records to return"),
    sentiment_filter: Optional[str] = Query(None, description="Filter by sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED)"),
    subreddit: Optional[str] = Query(None, description="Filter by subreddit")
):
    """Get sentiment analysis results with optional filtering"""
    try:
        if not processed_table:
            raise HTTPException(status_code=503, detail="Database not available")
            
        # Build scan parameters
        scan_kwargs = {'Limit': limit}
        
        # Add filters if provided
        filter_expressions = []
        
        if sentiment_filter:
            filter_expressions.append(Attr('sentiment').eq(sentiment_filter.upper()))
        
        if subreddit:
            filter_expressions.append(Attr('subreddit').eq(subreddit))
        
        # Combine filters with AND
        if filter_expressions:
            combined_filter = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined_filter = combined_filter & expr
            scan_kwargs['FilterExpression'] = combined_filter
        
        # Perform scan
        response = processed_table.scan(**scan_kwargs)
        items = response.get('Items', [])
        
        # Convert to dashboard-friendly format
        dashboard_format = []
        for item in items:
            dashboard_item = {
                'analysis_id': item.get('analysis_id', ''),
                'timestamp': format_timestamp(item.get('processed_timestamp')),
                'inputText': item.get('input_text', '')[:300],  # Truncate for display
                'sentiment': item.get('sentiment', 'NEUTRAL'),
                'confidence_score': decimal_to_float(item.get('confidence_score', 0)),
                'subreddit': item.get('subreddit', 'unknown'),
                'keywords_detected': item.get('keywords_detected', []),
                'original_post_id': item.get('original_post_id', ''),
                'analysis_metadata': decimal_to_float(item.get('analysis_metadata', {}))
            }
            dashboard_format.append(dashboard_item)
        
        # Sort by timestamp (newest first)
        dashboard_format.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return dashboard_format
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sentiments: {str(e)}")

@app.get("/sentiments/summary")
async def get_sentiment_summary():
    """Get aggregate sentiment statistics"""
    try:
        if not processed_table:
            raise HTTPException(status_code=503, detail="Database not available")
            
        # Scan all processed sentiment data
        response = processed_table.scan()
        items = response.get('Items', [])
        
        # Calculate statistics
        total_count = len(items)
        sentiment_counts = {'POSITIVE': 0, 'NEGATIVE': 0, 'NEUTRAL': 0, 'MIXED': 0}
        total_confidence = 0
        subreddit_counts = {}
        
        for item in items:
            # Count by sentiment
            sentiment = item.get('sentiment', 'NEUTRAL')
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1
            
            # Sum confidence scores
            confidence = decimal_to_float(item.get('confidence_score', 0))
            total_confidence += confidence
            
            # Count by subreddit
            subreddit = item.get('subreddit', 'unknown')
            subreddit_counts[subreddit] = subreddit_counts.get(subreddit, 0) + 1
        
        # Calculate average confidence
        average_confidence = total_confidence / total_count if total_count > 0 else 0
        
        return {
            'total_count': total_count,
            'positive_count': sentiment_counts['POSITIVE'],
            'negative_count': sentiment_counts['NEGATIVE'],
            'neutral_count': sentiment_counts['NEUTRAL'],
            'mixed_count': sentiment_counts['MIXED'],
            'average_confidence': round(average_confidence, 3),
            'subreddit_breakdown': subreddit_counts,
            'sentiment_distribution': {
                'positive_percentage': round((sentiment_counts['POSITIVE'] / total_count * 100), 1) if total_count > 0 else 0,
                'negative_percentage': round((sentiment_counts['NEGATIVE'] / total_count * 100), 1) if total_count > 0 else 0,
                'neutral_percentage': round((sentiment_counts['NEUTRAL'] / total_count * 100), 1) if total_count > 0 else 0,
                'mixed_percentage': round((sentiment_counts['MIXED'] / total_count * 100), 1) if total_count > 0 else 0
            },
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching summary: {str(e)}")

@app.get("/stats/processing")
async def get_processing_stats():
    """Get processing statistics and system metrics"""
    try:
        if not raw_posts_table or not processed_table:
            raise HTTPException(status_code=503, detail="Database not available")
            
        # Get raw posts count
        raw_response = raw_posts_table.scan(Select='COUNT')
        raw_count = raw_response.get('Count', 0)
        
        # Get processed posts count
        processed_response = processed_table.scan(Select='COUNT')
        processed_count = processed_response.get('Count', 0)
        
        # Calculate processing rate
        processing_rate = (processed_count / raw_count * 100) if raw_count > 0 else 0
        
        # Get recent processing activity (last 24 hours)
        recent_cutoff = datetime.now().timestamp() - (24 * 60 * 60)  # 24 hours ago
        
        recent_processed = processed_table.scan(
            FilterExpression=Attr('processed_timestamp').gte(Decimal(str(recent_cutoff))),
            Select='COUNT'
        )
        recent_count = recent_processed.get('Count', 0)
        
        return {
            'raw_posts_count': raw_count,
            'processed_posts_count': processed_count,
            'processing_rate_percent': round(processing_rate, 1),
            'unprocessed_count': raw_count - processed_count,
            'recent_24h_processed': recent_count,
            'last_updated': datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching processing stats: {str(e)}")

# Data models for scraping requests
class ScrapeRequest(BaseModel):
    analysis_type: str  # 'keywords', 'subreddits', or 'both'
    keywords: Optional[List[str]] = None
    subreddits: Optional[List[str]] = None
    posts_limit: int = 25

class SentimentProcessRequest(BaseModel):
    processing_mode: str = 'batch'
    batch_size: int = 50

# Global storage for job status (in production, use Redis or DynamoDB)
job_status = {}

@app.post("/scrape/start")
async def start_scraping(request: ScrapeRequest):
    """Start a new Reddit scraping job based on user input"""
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        job_status[job_id] = {
            'status': 'started',
            'progress': 0,
            'message': 'Initializing scraping job...',
            'start_time': datetime.now().isoformat(),
            'error': None
        }
        
        # Note: In Lambda, you might want to use SQS or Step Functions for long-running tasks
        # For now, we'll use background tasks (may timeout in Lambda)
        asyncio.create_task(run_scraping_job(job_id, request))
        
        return {
            'status': 'started',
            'job_id': job_id,
            'message': 'Scraping job started successfully'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")

@app.get("/scrape/status/{job_id}")
async def get_scraping_status(job_id: str):
    """Get the status of a scraping job"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_status[job_id]

async def run_scraping_job(job_id: str, request: ScrapeRequest):
    """Run the actual scraping job in background"""
    try:
        # Import your scraper (may need to be restructured for Lambda)
        from main import RedditScraperDynamoDB
        
        # Update status
        job_status[job_id].update({
            'status': 'running',
            'progress': 10,
            'message': 'Initializing Reddit scraper...'
        })
        
        # Initialize scraper
        scraper = RedditScraperDynamoDB()
        
        # Update status
        job_status[job_id].update({
            'progress': 20,
            'message': 'Starting data collection...'
        })
        
        results = {}
        
        # Handle subreddit scraping
        if request.analysis_type in ['subreddits', 'both'] and request.subreddits:
            job_status[job_id].update({
                'progress': 30,
                'message': f'Scraping {len(request.subreddits)} subreddits...'
            })
            
            subreddit_results = scraper.scrape_multiple_subreddits(
                request.subreddits,
                posts_per_subreddit=request.posts_limit
            )
            results['subreddits'] = subreddit_results
            
            job_status[job_id].update({
                'progress': 60,
                'message': 'Subreddit scraping complete'
            })
        
        # Handle keyword scraping
        if request.analysis_type in ['keywords', 'both'] and request.keywords:
            job_status[job_id].update({
                'progress': 70,
                'message': f'Searching for {len(request.keywords)} keywords...'
            })
            
            keyword_results = scraper.search_and_scrape_by_keywords(
                request.keywords,
                posts_per_keyword=request.posts_limit
            )
            results['keywords'] = keyword_results
            
            job_status[job_id].update({
                'progress': 90,
                'message': 'Keyword search complete'
            })
        
        # Job complete
        job_status[job_id].update({
            'status': 'completed',
            'progress': 100,
            'message': 'Scraping completed successfully',
            'end_time': datetime.now().isoformat(),
            'results': results
        })
        
    except Exception as e:
        # Job failed
        job_status[job_id].update({
            'status': 'failed',
            'progress': 0,
            'message': f'Scraping failed: {str(e)}',
            'error': str(e),
            'end_time': datetime.now().isoformat()
        })

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "message": "The requested endpoint does not exist",
            "available_endpoints": [
                "/", "/health", "/status", "/sentiments", "/sentiments/summary", 
                "/stats/processing", "/docs"
            ]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )

# =====================================
# LAMBDA HANDLER CONFIGURATION
# =====================================

# Create Lambda handler using Mangum
if LAMBDA_AVAILABLE:
    handler = Mangum(
        app,
        lifespan="off",  # Disable lifespan for Lambda
        api_gateway_base_path="/",  # Adjust based on your API Gateway setup
    )
    print("✅ Lambda handler created with Mangum")
else:
    handler = None
    print("⚠️ Lambda handler not available (Mangum not installed)")

# =====================================
# LOCAL DEVELOPMENT SERVER
# =====================================

def run_local_server():
    """Run the FastAPI server locally"""
    import uvicorn
    
    print("🚀 Starting Reddit Sentiment Analysis API...")
    print("📊 Dashboard: Open frontend/index.html in your browser")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🔍 API Root: http://localhost:8000/")
    print("💚 Health Check: http://localhost:8000/health")
    print("📊 Status: http://localhost:8000/status")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True  # Auto-reload on code changes
    )

if __name__ == "__main__":
    # Only run the local server if not in Lambda environment
    if not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        run_local_server()
    else:
        print("🔧 Running in Lambda environment")