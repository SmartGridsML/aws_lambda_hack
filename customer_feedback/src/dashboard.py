import os
import json
from datetime import datetime, timedelta
import boto3

dynamo = boto3.resource('dynamodb')
table = dynamo.Table(os.environ['SENTIMENT_TABLE'])

def lambda_handler(event, context):
    """
    Returns aggregated sentiment over the last hour:
      { positive: N, negative: M, neutral: P, mixed: Q, trend: [...] }
    """
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=1)).isoformat()

    # Query by timestamp range (scan for simplicity)
    resp = table.scan(
        FilterExpression='timestamp >= :cut',
        ExpressionAttributeValues={':cut': cutoff}
    )
    items = resp.get('Items', [])

    counts = {'POSITIVE':0, 'NEGATIVE':0, 'NEUTRAL':0, 'MIXED':0}
    trend = {}
    for it in items:
        s = it.get('sentiment')
        counts[s] = counts.get(s,0) + 1
        minute = it['timestamp'][:16]  # YYYY-MM-DDTHH:MM
        trend.setdefault(minute, {'POSITIVE':0,'NEGATIVE':0,'NEUTRAL':0,'MIXED':0})
        trend[minute][s] += 1

    return {
        'statusCode':200,
        'headers':{'Content-Type':'application/json','Access-Control-Allow-Origin':'*'},
        'body': json.dumps({
            'summary': counts,
            'trend': [
                {'minute': m, **trend[m]} for m in sorted(trend)
            ]
        })
    }
