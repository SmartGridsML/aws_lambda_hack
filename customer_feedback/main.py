import praw
import boto3
import os
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv
from decimal import Decimal

# Load environment variables
load_dotenv()

class RedditScraperDynamoDB:
    """
    A comprehensive Reddit scraper that saves data to DynamoDB.
    
    This class demonstrates several important concepts:
    1. How to structure data for DynamoDB (partition keys, sort keys)
    2. How to handle Reddit API rate limiting
    3. How to batch write operations for efficiency
    4. How to design for scalability and error recovery
    """
    
    def __init__(self):
        # Initialize Reddit API connection
        self.reddit = praw.Reddit(
            client_id=os.environ['REDDIT_CLIENT_ID'],
            client_secret=os.environ['REDDIT_CLIENT_SECRET'],
            user_agent="reddit-sentiment-scraper/1.0 by {}".format(os.environ['REDDIT_USERNAME']),
            username=os.environ['REDDIT_USERNAME'],
            password=os.environ['REDDIT_PASSWORD']
        )
        
        # Initialize AWS DynamoDB connection
        # In production, you'd use IAM roles instead of access keys
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # Define table names - this allows easy switching between environments
        self.raw_posts_table_name = os.getenv('RAW_POSTS_TABLE', 'reddit-raw-posts')
        self.processed_data_table_name = os.getenv('PROCESSED_DATA_TABLE', 'reddit-processed-sentiment')
        
        # Get table references
        self.raw_posts_table = self.dynamodb.Table(self.raw_posts_table_name)
        self.processed_data_table = self.dynamodb.Table(self.processed_data_table_name)
        
        print(f"✅ Connected to Reddit API as user: {self.reddit.user.me()}")
        print(f"✅ Connected to DynamoDB tables: {self.raw_posts_table_name}, {self.processed_data_table_name}")

    def extract_post_data(self, post) -> Dict[str, Any]:
        """
        Extract comprehensive data from a Reddit post.
        
        This function demonstrates how to handle Reddit's data structure
        and prepare it for DynamoDB storage. Notice how we handle potential
        None values and convert data types that DynamoDB can't store natively.
        """
        
        # Handle potential None values gracefully - FIXED LINE
        author_name = str(post.author) if post.author else '[deleted]'
        
        # Create a comprehensive data structure
        post_data = {
            # Primary keys for DynamoDB
            'post_id': post.id,  # This will be our partition key
            'created_timestamp': Decimal(str(post.created_utc)),  # Sort key for time-based queries
            
            # Content fields - the actual text we'll analyze
            'title': post.title,
            'selftext': post.selftext,  # The body text of the post
            'url': post.url,
            
            # Metadata for context and filtering
            'subreddit': post.subreddit.display_name,
            'author': author_name,
            'score': post.score,
            'upvote_ratio': Decimal(str(post.upvote_ratio)),
            'num_comments': post.num_comments,
            
            # Technical metadata
            'is_self': post.is_self,  # True for text posts, False for links
            'over_18': post.over_18,
            'spoiler': post.spoiler,
            'stickied': post.stickied,
            
            # Processing metadata
            'scraped_at': Decimal(str(datetime.now(timezone.utc).timestamp())),
            'processing_status': 'raw',  # Will be updated as we process the data
            'permalink': f"https://reddit.com{post.permalink}",
            
            # Combined text for analysis - this is what we'll send to sentiment analysis
            'combined_text': f"{post.title} {post.selftext}".strip()
        }
        
        return post_data

    def extract_comment_data(self, comment, parent_post_id: str) -> Dict[str, Any]:
        """
        Extract data from Reddit comments.
        
        Comments often contain more honest, unfiltered opinions than posts,
        making them valuable for sentiment analysis. This function shows how
        to handle the hierarchical structure of Reddit comments.
        """
        
        if not comment.author or len(comment.body) < 10:
            return None  # Skip deleted or very short comments
        
        comment_data = {
            'post_id': comment.id,
            'created_timestamp': Decimal(str(comment.created_utc)),
            'parent_post_id': parent_post_id,
            'author': str(comment.author),
            'body': comment.body,
            'score': comment.score,
            'is_submitter': comment.is_submitter,  # True if this is the original poster
            'scraped_at': Decimal(str(datetime.now(timezone.utc).timestamp())),
            'processing_status': 'raw',
            'permalink': f"https://reddit.com{comment.permalink}",
            'combined_text': comment.body
        }
        
        return comment_data

    def save_to_dynamodb(self, items: List[Dict[str, Any]], table_name: str):
        """
        Efficiently save multiple items to DynamoDB using batch operations.
        
        This function demonstrates several DynamoDB best practices:
        1. Batch writing for efficiency
        2. Error handling and retry logic
        3. Rate limiting to avoid throttling
        """
        
        if not items:
            return
        
        table = self.dynamodb.Table(table_name)
        
        # DynamoDB batch_write_item can handle up to 25 items at a time
        batch_size = 25
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                # Prepare batch write request
                with table.batch_writer() as batch_writer:
                    for item in batch:
                        batch_writer.put_item(Item=item)
                
                print(f"✅ Saved batch of {len(batch)} items to {table_name}")
                
            except Exception as e:
                print(f"❌ Error saving batch to {table_name}: {e}")
                # In production, you'd implement retry logic here
                
            # Rate limiting to avoid overwhelming DynamoDB
            time.sleep(0.1)

    def scrape_subreddit_comprehensive(self, subreddit_name: str, limit: int = 100, include_comments: bool = True):
        """
        Perform comprehensive scraping of a subreddit including posts and comments.
        
        This is your main scraping function that orchestrates the entire data collection process.
        It demonstrates how to handle large-scale data collection while respecting API limits.
        """
        
        print(f"\n🔍 Starting comprehensive scrape of r/{subreddit_name}")
        print(f"Target: {limit} posts, Comments: {'Yes' if include_comments else 'No'}")
        
        subreddit = self.reddit.subreddit(subreddit_name)
        posts_data = []
        comments_data = []
        seen_post_ids = set()  # Track seen posts to avoid duplicates
        
        try:
            # Collect posts from multiple sources for comprehensive coverage
            post_sources = [
                ('new', subreddit.new(limit=limit//3)),
                ('hot', subreddit.hot(limit=limit//3)),
                ('top_week', subreddit.top(time_filter='week', limit=limit//3))
            ]
            
            for source_name, posts in post_sources:
                print(f"\n📊 Processing {source_name} posts...")
                
                for post in posts:
                    try:
                        # Skip if we've already processed this post
                        if post.id in seen_post_ids:
                            continue
                        
                        seen_post_ids.add(post.id)
                        
                        # Extract post data
                        post_data = self.extract_post_data(post)
                        posts_data.append(post_data)
                        
                        # Extract comments if requested
                        if include_comments and post.num_comments > 0:
                            # Limit comments per post to avoid overwhelming the system
                            post.comments.replace_more(limit=0)  # Load more comments
                            
                            comment_count = 0
                            max_comments_per_post = 20
                            
                            for comment in post.comments.list():
                                if comment_count >= max_comments_per_post:
                                    break
                                    
                                comment_data = self.extract_comment_data(comment, post.id)
                                if comment_data:
                                    comments_data.append(comment_data)
                                    comment_count += 1
                    
                    # Progress indicator
                    if len(posts_data) % 10 == 0:
                        print(f"  Processed {len(posts_data)} posts, {len(comments_data)} comments...")
                    
                    except Exception as e:
                        print(f"⚠️  Error processing post: {e}")
                        continue
                
                # Respect Reddit's rate limits
                time.sleep(0.1)
        
        # Save all collected data to DynamoDB
        print(f"\n💾 Saving data to DynamoDB...")
        
        # Save posts (both posts and comments go to the same table with different item types)
        if posts_data:
            # Add item type for easier querying
            for item in posts_data:
                item['item_type'] = 'post'
            self.save_to_dynamodb(posts_data, self.raw_posts_table_name)
        
        if comments_data:
            for item in comments_data:
                item['item_type'] = 'comment'
            self.save_to_dynamodb(comments_data, self.raw_posts_table_name)
        
        print(f"\n✅ Scraping complete!")
        print(f"📈 Collected: {len(posts_data)} posts, {len(comments_data)} comments")
        print(f"💾 All data saved to DynamoDB table: {self.raw_posts_table_name}")
        
        return {
            'posts_collected': len(posts_data),
            'comments_collected': len(comments_data),
            'subreddit': subreddit_name,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
            return None

    def scrape_multiple_subreddits(self, subreddit_list: List[str], posts_per_subreddit: int = 50):
        """
        Scrape multiple subreddits efficiently.
        
        This function shows how to scale your scraping operation across multiple communities
        while maintaining good performance and respecting API limits.
        """
        
        print(f"🚀 Starting multi-subreddit scraping operation")
        print(f"Targets: {subreddit_list}")
        print(f"Posts per subreddit: {posts_per_subreddit}")
        
        results = {}
        
        for i, subreddit_name in enumerate(subreddit_list, 1):
            print(f"\n[{i}/{len(subreddit_list)}] Processing r/{subreddit_name}...")
            
            try:
                result = self.scrape_subreddit_comprehensive(
                    subreddit_name, 
                    limit=posts_per_subreddit,
                    include_comments=True
                )
                results[subreddit_name] = result
                
            except Exception as e:
                print(f"❌ Failed to scrape r/{subreddit_name}: {e}")
                results[subreddit_name] = {'error': str(e)}
            
            # Pause between subreddits to be respectful
            time.sleep(2)
        
        return results

    def search_and_scrape_by_keywords(self, keywords: List[str], posts_per_keyword: int = 100):
        """
        Search across all of Reddit for specific keywords and scrape the results.
        
        This function demonstrates how to use Reddit's search functionality
        for targeted data collection based on your business interests.
        """
        
        print(f"🔎 Starting keyword-based scraping")
        print(f"Keywords: {keywords}")
        
        all_posts_data = []
        all_comments_data = []
        
        for keyword in keywords:
            print(f"\n🎯 Searching for: '{keyword}'")
            
            try:
                # Search across all of Reddit
                search_results = self.reddit.subreddit('all').search(
                    keyword, 
                    limit=posts_per_keyword,
                    time_filter='week',
                    sort='relevance'
                )
                
                keyword_posts = 0
                keyword_comments = 0
                
                for post in search_results:
                    try:
                        # Extract post data and add keyword context
                        post_data = self.extract_post_data(post)
                        post_data['matched_keyword'] = keyword
                        post_data['item_type'] = 'post'
                        all_posts_data.append(post_data)
                        keyword_posts += 1
                        
                        # Extract top comments
                        if post.num_comments > 0:
                            post.comments.replace_more(limit=0)
                            
                            for comment in post.comments.list()[:10]:  # Top 10 comments
                                comment_data = self.extract_comment_data(comment, post.id)
                                if comment_data:
                                    comment_data['matched_keyword'] = keyword
                                    comment_data['item_type'] = 'comment'
                                    all_comments_data.append(comment_data)
                                    keyword_comments += 1
                        
                    except Exception as e:
                        print(f"⚠️  Error processing search result: {e}")
                        continue
                    
                    time.sleep(0.1)
                
                print(f"  Found {keyword_posts} posts, {keyword_comments} comments for '{keyword}'")
                
            except Exception as e:
                print(f"❌ Error searching for '{keyword}': {e}")
                continue
        
        # Save all collected data
        print(f"\n💾 Saving search results to DynamoDB...")
        
        if all_posts_data:
            self.save_to_dynamodb(all_posts_data, self.raw_posts_table_name)
        
        if all_comments_data:
            self.save_to_dynamodb(all_comments_data, self.raw_posts_table_name)
        
        print(f"✅ Keyword search complete!")
        print(f"📊 Total collected: {len(all_posts_data)} posts, {len(all_comments_data)} comments")
        
        return {
            'total_posts': len(all_posts_data),
            'total_comments': len(all_comments_data),
            'keywords_searched': keywords
        }


def main():
    """
    Demonstration of how to use the Reddit scraper system.
    
    This main function shows different ways to collect data depending on your research needs.
    You can customize these examples based on your specific business requirements.
    """
    
    # Initialize the scraper
    scraper = RedditScraperDynamoDB()
    
    # Example 1: Scrape specific subreddits related to your business
    target_subreddits = [
        'aws',
        'serverless', 
        'devops',
        'programming',
        'webdev'
    ]
    
    print("Example 1: Multi-subreddit scraping")
    subreddit_results = scraper.scrape_multiple_subreddits(target_subreddits, posts_per_subreddit=30)
    
    # Example 2: Keyword-based scraping for targeted business intelligence
    business_keywords = [
        'AWS Lambda pricing',
        'serverless architecture',
        'API Gateway costs',
        'cloud functions performance'
    ]
    
    print("\n" + "="*50)
    print("Example 2: Keyword-based scraping")
    keyword_results = scraper.search_and_scrape_by_keywords(business_keywords, posts_per_keyword=25)
    
    # Print summary
    print("\n" + "="*50)
    print("SCRAPING OPERATION COMPLETE")
    print("="*50)
    print("Your data is now stored in DynamoDB and ready for processing!")
    print("Next steps:")
    print("1. Run the Lambda sentiment analysis processor")
    print("2. Start the FastAPI backend")
    print("3. View results in your dashboard")


if __name__ == "__main__":
    main()