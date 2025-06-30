# Reddit Sentiment Discovery Dashboard

A local prototype for discovering and analyzing sentiment in Reddit communities around keywords like **AWS Lambda**, **serverless**, and **API Gateway**, with a minimal FastAPI backend and static HTML dashboard.

---

## 🚀 Overview

This project helps you:
1. **Discover** subreddits where your target keywords appear most often.  
2. **Fetch** post content (title, body, score, comments) via the Reddit API.  
3. **Analyze** sentiment with a simple rule-based function (in `lambda_func.py`).  
4. **Store** raw and processed data in DynamoDB (via `dynamo.py`).  
5. **Serve** data over HTTP with a FastAPI app (`fastapi_app.py`).  
6. **Visualize** trends in a static dashboard (`frontend/index.html`).

---

## 📁 Project Structure

.
├── dynamo.py # DynamoDB setup and helper functions
├── lambda_func.py # Post-processing: rule-based sentiment analysis
├── main.py # Discovery & ingestion script (scrapes & saves posts)
├── fastapi_app.py # Local HTTP API for querying raw & sentiment data
├── frontend/
│ └── index.html # Static dashboard (charts & stats)
├── test.py # (Placeholder) for unit/integration tests


markdown


---

## ⚙️ Prerequisites

- **Python 3.9+**  
- **pip**  
- **AWS account** with DynamoDB (or run [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html))  
- **Reddit API credentials** (script app): `CLIENT_ID`, `CLIENT_SECRET`, `USERNAME`, `PASSWORD`  
- **Environment file** `.env` containing:

  ```dotenv
  REDDIT_CLIENT_ID=…
  REDDIT_CLIENT_SECRET=…
  REDDIT_USERNAME=…
  REDDIT_PASSWORD=…
  AWS_ACCESS_KEY_ID=…
  AWS_SECRET_ACCESS_KEY=…
  AWS_DEFAULT_REGION=…
🔧 Installation & Setup
Clone the repo

```bash
git clone https://github.com/your-org/reddit-sentiment-dashboard.git
cd reddit-sentiment-dashboard
Install dependencies```

```bash
pip install -r requirements.txt```
Initialize DynamoDB tables (local or AWS)

bash

python dynamo.py
Fetch & store Reddit posts

bash

python main.py
Run sentiment analysis

bash

python lambda_func.py
Start the API server

bash

uvicorn fastapi_app:app --reload
Open the dashboard
In your browser, navigate to frontend/index.html and point the JS client at http://localhost:8000.

🛠 Usage
Discover new keywords: edit the keywords list in main.py and re-run.

Adjust sample size & timeframe: tweak sample_size and time_filter in main.py.

View raw data: use the FastAPI endpoints:

GET /posts → all raw posts

GET /sentiments → posts with sentiment labels

Visualize: refresh index.html to see updated charts.

✅ What It Fulfills
Data Collection: pulls publicly available Reddit content.

Processing: local sentiment analysis (rule-based).

Storage: uses DynamoDB for time-series and metadata.

Visualization: simple HTML/JS dashboard.

🚧 Limitations & Next Steps
Not yet serverless: requires manual runs & local server

Rule-based sentiment: swap in Amazon Comprehend for more accuracy

Automation: deploy each handler as AWS Lambda behind API Gateway & DynamoDB Streams

Security: move secrets to AWS Secrets Manager or Parameter Store

Testing: flesh out test.py with pytest + moto mocks