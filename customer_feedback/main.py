# main.py
import os
from dotenv import load_dotenv
import praw
import json
from datetime import datetime
from collections import defaultdict
import time
import logging
import sys

load_dotenv()

# Setup logging first
def setup_logging(log_file='app.log', level=logging.INFO):
    logger = logging.getLogger()
    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    fmt = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    ch.setFormatter(fmt)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(level)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)

setup_logging(level=logging.INFO)
log = logging.getLogger(__name__)

# Reddit setup
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent="python:SentimentMonitor:v0.1 (by /u/{})".format(os.getenv('REDDIT_USERNAME')),
    username=os.getenv('REDDIT_USERNAME'),
    password=os.getenv('REDDIT_PASSWORD')
)

def save_json(data, filename_prefix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{filename_prefix}_{timestamp}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Saved {filename_prefix} to {path}")

def discover_subreddits_by_content_analysis(keywords, sample_size=1000, time_filter='month'):
    subreddit_keyword_frequency = defaultdict(lambda: defaultdict(int))
    subreddit_metadata = {}
    subreddit_posts = defaultdict(list)    # NEW: collect posts per subreddit
    
    log.info(f"Starting content analysis for {len(keywords)} keywords")
    
    for i, keyword in enumerate(keywords, 1):
        log.info(f"[{i}/{len(keywords)}] Searching for '{keyword}'")
        search_results = reddit.subreddit('all').search(
            keyword, limit=sample_size, time_filter=time_filter, sort='relevance'
        )
        
        count = 0
        for post in search_results:
            sr = post.subreddit.display_name
            subreddit_keyword_frequency[sr][keyword] += 1

            # --- NEW CODE: store the post content ---
            subreddit_posts[sr].append({
                'id'         : post.id,
                'title'      : post.title,
                'selftext'   : post.selftext,        # body text
                'url'        : post.url,             # link or post permalink
                'created_utc': post.created_utc,
                'score'      : post.score,           # upvotes - downvotes
                'num_comments': post.num_comments,   # comment count
                'keyword'    : keyword               # which keyword matched this post
            })

            if sr not in subreddit_metadata:
                try:
                    sb = reddit.subreddit(sr)
                    subreddit_metadata[sr] = {
                        'name'       : sr,
                        'title'      : sb.title,
                        'subscribers': sb.subscribers,
                        'description': sb.public_description,
                        'over_18'    : sb.over18,
                        'created_utc': sb.created_utc,
                        'url'        : f"https://reddit.com/r/{sr}"
                    }
                except Exception as e:
                    log.warning(f"Could not fetch metadata for r/{sr}: {e}")
                    subreddit_metadata[sr] = {
                        'name': sr,
                        'title': '<private>',
                        'subscribers': 0,
                        'description': '',
                        'over_18': False,
                        'created_utc': 0,
                        'url': f"https://reddit.com/r/{sr}"
                    }
            
            count += 1
            if count % 50 == 0:
                log.info(f"  Processed {count} posts for '{keyword}'")
            time.sleep(0.05)  # rate-limit

        log.info(f"Completed '{keyword}' ({count} posts)")

    # At the end of discovery, save out the raw data
    save_json(subreddit_keyword_frequency,  "frequency")
    save_json(subreddit_metadata,            "metadata")
    save_json(subreddit_posts,               "posts")    # NEW: persist post content

    log.info(f"Collected {len(subreddit_posts)} subreddits with post content")
    total_posts = sum(len(posts) for posts in subreddit_posts.values())
    log.info(f"Total posts collected: {total_posts}")

    return subreddit_keyword_frequency, subreddit_metadata, subreddit_posts

def rank_subreddits_by_relevance(freq, meta, min_mentions=3, min_subscribers=100):
    rankings = {}
    for sr, kw_counts in freq.items():
        if sr not in meta: 
            continue
        
        total = sum(kw_counts.values())
        subs = meta[sr]['subscribers']
        if total < min_mentions or subs < min_subscribers: 
            continue

        diversity = len(kw_counts)
        density = (total / subs) * 1000 if subs else 0
        
        # Enhanced scoring with engagement factors
        score = (
            total * 10 +           # raw mentions
            diversity * 5 +        # keyword diversity
            (15 if 1000 <= subs <= 50000 else 
             10 if subs <= 200000 else 5)  # subscriber sweet spot
        )
        
        rankings[sr] = {
            'total_mentions': total,
            'subscribers': subs,
            'diversity': diversity,
            'density': density,
            'score': score,
            'keyword_breakdown': dict(kw_counts)  # detailed breakdown
        }
    
    log.info(f"Ranked {len(rankings)} subreddits")
    return rankings

def main():
    keywords = ['AWS Lambda', 'serverless', 'API Gateway']
    
    # Enhanced discovery with content collection
    freq, meta, posts = discover_subreddits_by_content_analysis(
        keywords,
        sample_size=200,
        time_filter='week'
    )
    
    # Rank subreddits
    rankings = rank_subreddits_by_relevance(freq, meta, min_mentions=3, min_subscribers=100)
    save_json(rankings, "rankings")
    
    # Display top 10 results
    log.info("\n=== TOP 10 SUBREDDITS FOR CONTENT ===")
    for i, (sr, data) in enumerate(sorted(rankings.items(), key=lambda x: -x[1]['score'])[:10], 1):
        post_count = len(posts.get(sr, []))
        log.info(f"{i}. r/{sr}")
        log.info(f"   Score: {data['score']:.1f} | Posts: {post_count} | Subs: {data['subscribers']:,}")
        log.info(f"   Keywords: {data['keyword_breakdown']}")
        log.info("")
    
    log.info("Analysis complete.")

if __name__ == "__main__":
    main()