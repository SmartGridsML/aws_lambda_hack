import os
import json
import boto3

comprehend = boto3.client('comprehend')
dynamo = boto3.resource('dynamodb')
table = dynamo.Table(os.environ['SENTIMENT_TABLE'])

def lambda_handler(event, context):
    """
    Triggered by DynamoDB Stream on new items.
    Calls Comprehend.DetectSentiment and updates the same record with sentiment score.
    """
    for record in event['Records']:
        if record['eventName'] != 'INSERT':
            continue

        new_image = record['dynamodb']['NewImage']
        pk = new_image['pk']['S']
        text = new_image['text']['S']

        resp = comprehend.detect_sentiment(Text=text, LanguageCode='en')
        sentiment = resp['Sentiment']
        scores = resp['SentimentScore']

        # Update item with sentiment and scores
        table.update_item(
            Key={'pk': pk, 'timestamp': new_image['timestamp']['S']},
            UpdateExpression='SET sentiment = :s, scores = :sc',
            ExpressionAttributeValues={
                ':s': sentiment,
                ':sc': {k: float(v) for k,v in scores.items()}
            }
        )
