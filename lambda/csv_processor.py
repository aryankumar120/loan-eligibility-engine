"""
AWS Lambda function to process CSV files uploaded to S3
Triggered by S3 ObjectCreated event
"""
import json
import csv
import boto3
import os
import logging
from io import StringIO
import requests
from db_utils import (
    insert_users_batch,
    create_csv_upload_record,
    update_csv_upload_status
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')


def validate_user_data(row):
    """
    Validate and clean user data from CSV row

    Returns:
        Dict with validated user data or None if validation fails
    """
    try:
        # Required fields
        email = row.get('email', '').strip()
        if not email or '@' not in email:
            raise ValueError("Invalid email")

        # Parse and validate numeric fields
        monthly_income = float(row.get('monthly_income', 0))
        credit_score = int(row.get('credit_score', 0))
        age = int(row.get('age', 0))

        # Validate ranges
        if credit_score < 300 or credit_score > 850:
            raise ValueError(f"Credit score {credit_score} out of range (300-850)")

        if age < 18 or age > 100:
            raise ValueError(f"Age {age} out of range (18-100)")

        if monthly_income < 0:
            raise ValueError(f"Monthly income cannot be negative")

        employment_status = row.get('employment_status', '').strip()

        return {
            'email': email,
            'monthly_income': monthly_income,
            'credit_score': credit_score,
            'employment_status': employment_status,
            'age': age
        }

    except Exception as e:
        logger.warning(f"Validation failed for row: {str(e)}")
        return None


def process_csv_file(bucket, key):
    """
    Download and process CSV file from S3

    Returns:
        Tuple of (total_records, processed_records, failed_records, errors)
    """
    logger.info(f"Processing CSV file: s3://{bucket}/{key}")

    # Download file from S3
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to download file from S3: {str(e)}")
        raise

    # Parse CSV
    csv_file = StringIO(csv_content)
    csv_reader = csv.DictReader(csv_file)

    users_data = []
    total_records = 0
    invalid_records = 0
    errors = []

    for row in csv_reader:
        total_records += 1
        validated_data = validate_user_data(row)

        if validated_data:
            users_data.append(validated_data)
        else:
            invalid_records += 1
            errors.append(f"Row {total_records}: Invalid data")

    logger.info(f"Parsed {total_records} records, {len(users_data)} valid, {invalid_records} invalid")

    # Insert users into database
    if users_data:
        success_count, failed_count, db_errors = insert_users_batch(users_data)
        errors.extend(db_errors)
        processed_records = success_count
        failed_records = invalid_records + failed_count
    else:
        processed_records = 0
        failed_records = total_records

    return total_records, processed_records, failed_records, errors


def trigger_matching_workflow(bucket, key):
    """
    Trigger the n8n matching workflow via webhook
    """
    webhook_url = os.environ.get('N8N_WEBHOOK_URL')

    if not webhook_url:
        logger.warning("N8N_WEBHOOK_URL not configured, skipping workflow trigger")
        return

    try:
        payload = {
            'event': 'csv_processed',
            'bucket': bucket,
            'key': key,
            'timestamp': json.dumps({}, default=str)
        }

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            logger.info("Successfully triggered n8n matching workflow")
        else:
            logger.warning(f"Failed to trigger n8n workflow: {response.status_code}")

    except Exception as e:
        logger.error(f"Error triggering n8n workflow: {str(e)}")
        # Don't raise - this is non-critical


def handler(event, context):
    """
    Lambda handler function triggered by S3 ObjectCreated event
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract S3 event details
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        file_name = os.path.basename(key)

        logger.info(f"Processing file: {file_name} from bucket: {bucket}")

        # Create upload record
        upload_id = create_csv_upload_record(file_name, key)
        logger.info(f"Created upload record with ID: {upload_id}")

        # Process the CSV file
        try:
            total_records, processed_records, failed_records, errors = process_csv_file(bucket, key)

            # Update upload status
            update_csv_upload_status(
                upload_id=upload_id,
                status='completed',
                total_records=total_records,
                processed_records=processed_records,
                failed_records=failed_records,
                error_message='; '.join(errors[:10]) if errors else None  # Limit error message size
            )

            logger.info(f"Processing completed: {processed_records}/{total_records} records successful")

            # Trigger n8n matching workflow
            trigger_matching_workflow(bucket, key)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'CSV processed successfully',
                    'upload_id': upload_id,
                    'total_records': total_records,
                    'processed_records': processed_records,
                    'failed_records': failed_records
                })
            }

        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            update_csv_upload_status(
                upload_id=upload_id,
                status='failed',
                error_message=str(e)
            )
            raise

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Failed to process CSV',
                'error': str(e)
            })
        }
