"""
Database initialization script
Run this script to create tables and initial schema in RDS PostgreSQL
"""
import psycopg2
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_sql_file(filename):
    """Read SQL file content"""
    with open(filename, 'r') as f:
        return f.read()


def init_database(host, port, database, user, password):
    """
    Initialize the database with schema

    Args:
        host: RDS endpoint
        port: Database port
        database: Database name
        user: Database username
        password: Database password
    """
    try:
        # Connect to database
        logger.info(f"Connecting to database at {host}:{port}")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )

        cursor = conn.cursor()

        # Read and execute schema file
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        logger.info(f"Reading schema from {schema_path}")
        schema_sql = read_sql_file(schema_path)

        logger.info("Executing schema SQL...")
        cursor.execute(schema_sql)
        conn.commit()

        logger.info("Database initialized successfully!")

        # Verify tables were created
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        logger.info("Created tables:")
        for table in tables:
            logger.info(f"  - {table[0]}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False


def main():
    """Main function to run database initialization"""
    # Get database credentials from environment or arguments
    db_host = os.environ.get('DB_HOST') or input("Enter DB host (RDS endpoint): ")
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'loan_eligibility')
    db_user = os.environ.get('DB_USER', 'admin')
    db_password = os.environ.get('DB_PASSWORD') or input("Enter DB password: ")

    logger.info(f"Initializing database '{db_name}' at {db_host}:{db_port}")

    success = init_database(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )

    if success:
        logger.info("✅ Database initialization completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Database initialization failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
