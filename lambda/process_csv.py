"""
Lambda function to process CSV files uploaded to S3.
Triggered by S3 events, parses CSV, stores data in RDS PostgreSQL.
"""
import json
import csv
import boto3
import psycopg2
import os
from io import StringIO
import urllib.parse
from datetime import datetime

# Environment variables
DB_HOST = os.environ['DB_HOST']
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ['DB_NAME']
DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', '')

s3_client = boto3.client('s3')

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode='require'
    )

def lambda_handler(event, context):
    """
    Main handler for S3 CSV upload events
    """
    try:
        # Get S3 bucket and key from event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        print(f"Processing file: s3://{bucket}/{key}")

        # Download CSV from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')

        # Parse CSV
        csv_file = StringIO(csv_content)
        csv_reader = csv.DictReader(csv_file)

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()

        users_inserted = 0
        users_skipped = 0

        # Insert users into database
        for row in csv_reader:
            try:
                cursor.execute("""
                    INSERT INTO users (user_id, name, email, monthly_income, credit_score, employment_status, age)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                """, (
                    row.get('user_id', ''),
                    row.get('name', ''),
                    row.get('email', ''),
                    float(row.get('monthly_income', 0)),
                    int(row.get('credit_score', 0)),
                    row.get('employment_status', ''),
                    int(row.get('age', 0))
                ))

                if cursor.rowcount > 0:
                    users_inserted += 1
                else:
                    users_skipped += 1

            except Exception as e:
                print(f"Error inserting row: {e}")
                users_skipped += 1
                continue

        # Commit transaction
        conn.commit()
        cursor.close()
        conn.close()

        print(f"Successfully processed: {users_inserted} inserted, {users_skipped} skipped")

        # Trigger n8n webhook (Workflow B) if configured
        if N8N_WEBHOOK_URL:
            try:
                import requests
                webhook_payload = {
                    'event': 'csv_processed',
                    'users_inserted': users_inserted,
                    'users_skipped': users_skipped,
                    'file': key,
                    'bucket': bucket,
                    'timestamp': str(datetime.now())
                }
                print(f"Triggering n8n webhook: {N8N_WEBHOOK_URL}")
                response = requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=10)
                print(f"n8n webhook response: {response.status_code}")
            except Exception as e:
                print(f"Failed to trigger n8n webhook: {e}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'CSV processed successfully',
                'users_inserted': users_inserted,
                'users_skipped': users_skipped,
                'file': key
            })
        }

    except Exception as e:
        print(f"Error processing CSV: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
