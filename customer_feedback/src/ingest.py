import os
import uuid
import json
import boto3
from datetime import datetime

dynamo = boto3.resource('dynamodb')
table = dynamo.Table(os.environ['SENTIMENT_TABLE'])

def lambda_handler(event, context):
    """
    Receives JSON payload:
      { "text": "...user feedback text...", "source": "...optional label..." }
    Stores with a generated UUID and timestamp; DynamoDB Stream triggers sentiment.
    """
    body = json.loads(event.get('body', '{}'))
    text = body.get('text')
    source = body.get('source', 'public')

    if not text:
        return { 'statusCode': 400, 'body': json.dumps({'error': 'Missing "text"'}) }

    item = {
        'pk': f'fb#{uuid.uuid4()}',
        'timestamp': datetime.utcnow().isoformat(),
        'text': text,
        'source': source,
        'sentiment': 'PENDING'
    }
    table.put_item(Item=item)
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Feedback received', 'id': item['pk']})
    }
