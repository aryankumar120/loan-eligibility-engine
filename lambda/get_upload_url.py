"""
AWS Lambda function to generate presigned S3 upload URLs
This provides a secure way for the UI to upload CSV files directly to S3
"""
import json
import boto3
import os
import logging
from datetime import datetime
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def handler(event, context):
    """
    Lambda handler to generate presigned S3 upload URL

    Query parameters:
        - filename: Original filename (optional)
        - content_type: Content type (default: text/csv)

    Returns:
        Presigned URL for uploading CSV file to S3
    """
    logger.info(f"Received request: {json.dumps(event)}")

    try:
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        original_filename = query_params.get('filename', 'upload.csv')
        content_type = query_params.get('content_type', 'text/csv')

        # Validate file extension
        if not original_filename.lower().endswith('.csv'):
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Only CSV files are allowed'
                })
            }

        # Generate unique key for S3
        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"uploads/{timestamp}-{unique_id}-{original_filename}"

        bucket_name = os.environ['CSV_BUCKET']

        # Generate presigned POST URL
        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket_name,
            Key=s3_key,
            Fields={
                'Content-Type': content_type
            },
            Conditions=[
                {'Content-Type': content_type},
                ['content-length-range', 1, 10485760]  # 1 byte to 10MB
            ],
            ExpiresIn=3600  # URL valid for 1 hour
        )

        logger.info(f"Generated presigned URL for key: {s3_key}")

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'upload_url': presigned_post['url'],
                'fields': presigned_post['fields'],
                's3_key': s3_key,
                'bucket': bucket_name,
                'expires_in': 3600
            })
        }

    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'error': 'Failed to generate upload URL',
                'message': str(e)
            })
        }
