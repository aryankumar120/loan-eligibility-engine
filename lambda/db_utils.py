"""
Database utility functions for PostgreSQL connection and operations
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_db_connection():
    """
    Create and return a database connection using environment variables
    """
    try:
        conn = psycopg2.connect(
            host=os.environ['DB_HOST'],
            port=os.environ.get('DB_PORT', '5432'),
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            connect_timeout=10
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise


@contextmanager
def get_db_cursor(cursor_factory=None):
    """
    Context manager for database cursor with automatic connection cleanup
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=cursor_factory)
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database operation failed: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def insert_users_batch(users_data):
    """
    Insert multiple users into the database

    Args:
        users_data: List of dictionaries containing user data

    Returns:
        Tuple of (success_count, failed_count, errors)
    """
    success_count = 0
    failed_count = 0
    errors = []

    with get_db_cursor() as cursor:
        for user in users_data:
            try:
                cursor.execute("""
                    INSERT INTO users (email, monthly_income, credit_score, employment_status, age)
                    VALUES (%(email)s, %(monthly_income)s, %(credit_score)s, %(employment_status)s, %(age)s)
                    ON CONFLICT (email)
                    DO UPDATE SET
                        monthly_income = EXCLUDED.monthly_income,
                        credit_score = EXCLUDED.credit_score,
                        employment_status = EXCLUDED.employment_status,
                        age = EXCLUDED.age,
                        updated_at = CURRENT_TIMESTAMP
                """, user)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to insert user {user.get('email', 'unknown')}: {str(e)}")
                logger.error(f"Error inserting user: {str(e)}")

    return success_count, failed_count, errors


def update_csv_upload_status(upload_id, status, total_records=None, processed_records=None,
                             failed_records=None, error_message=None):
    """
    Update the status of a CSV upload
    """
    with get_db_cursor() as cursor:
        update_fields = ["status = %s"]
        values = [status]

        if total_records is not None:
            update_fields.append("total_records = %s")
            values.append(total_records)

        if processed_records is not None:
            update_fields.append("processed_records = %s")
            values.append(processed_records)

        if failed_records is not None:
            update_fields.append("failed_records = %s")
            values.append(failed_records)

        if error_message is not None:
            update_fields.append("error_message = %s")
            values.append(error_message)

        if status == 'completed' or status == 'failed':
            update_fields.append("processed_at = CURRENT_TIMESTAMP")

        values.append(upload_id)

        query = f"""
            UPDATE csv_uploads
            SET {', '.join(update_fields)}
            WHERE upload_id = %s
        """

        cursor.execute(query, values)


def create_csv_upload_record(file_name, s3_key):
    """
    Create a record for a new CSV upload

    Returns:
        upload_id
    """
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT INTO csv_uploads (file_name, s3_key, status)
            VALUES (%s, %s, 'pending')
            RETURNING upload_id
        """, (file_name, s3_key))

        result = cursor.fetchone()
        return result[0] if result else None


def get_newly_added_users(limit=None):
    """
    Get recently added users for matching
    """
    with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
        query = """
            SELECT user_id, email, monthly_income, credit_score, employment_status, age
            FROM users
            ORDER BY created_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        return cursor.fetchall()
