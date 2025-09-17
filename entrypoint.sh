#!/bin/bash

# Exit on any error
set -e

echo "Starting Django ecommerce application..."

# Wait for database to be ready
echo "Waiting for database to be ready..."
python << END
import sys
import time
import os
import MySQLdb

def wait_for_db():
    max_attempts = 30
    attempt = 0
    
    # Get database connection details from environment variables
    host = os.environ.get('DATABASE_HOST', 'db')
    port = int(os.environ.get('DATABASE_PORT', '3306'))
    user = os.environ.get('DATABASE_USER', 'myproject_user')
    password = os.environ.get('DATABASE_PASSWORD', 'StrongAppPW123!')
    database = os.environ.get('DATABASE_NAME', 'myproject_db')
    
    while attempt < max_attempts:
        try:
            # Try to connect to the database
            connection = MySQLdb.connect(
                host=host,
                port=port,
                user=user,
                passwd=password,
                db=database
            )
            connection.close()
            print("Database is ready!")
            return True
        except Exception as e:
            attempt += 1
            print(f"Database not ready (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(2)
    
    print("Database is not ready after maximum attempts")
    return False

wait_for_db()
END

# Run database migrations
echo "Running database migrations..."
python manage.py makemigrations shop --noinput
python manage.py makemigrations --noinput
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "Creating superuser if it doesn't exist..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
END

# Collect static files (already done in Dockerfile, but just in case)
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Django setup completed successfully!"

# Execute the main command
exec "$@"
