import json
import os
import pytest
import boto3
import importlib
from unittest.mock import patch, MagicMock
from moto import mock_aws

# --- Import the handler logic ---
handler_module = importlib.import_module("lambda.handler")
main = handler_module.main

@pytest.fixture(autouse=True)
def aws_env():
    """Sets every environment variable your handler.py expects to find."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
    os.environ["AWS_REGION"] = "eu-central-1"
    
    # These were likely missing in your previous run:
    os.environ["DB_SECRET_ARN"] = "arn:aws:secretsmanager:eu-central-1:1:secret:test"
    os.environ["DB_NAME"] = "postgres"
    os.environ["BUCKET_NAME"] = "test-bucket"

VALID_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

@mock_aws
@patch('pg8000.native.Connection')
@patch('lambda.handler.get_secrets')
def test_create_item_and_upload_s3(mock_secrets, mock_conn, aws_env):
    # 1. Setup Mock S3
    s3 = boto3.client("s3", region_name="eu-central-1")
    s3.create_bucket(Bucket="test-bucket", CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    
    # 2. Setup Mock Secrets (Matches your handler's keys)
    mock_secrets.return_value = {
        "username": "u", 
        "password": "p", 
        "host": "h", 
        "port": "5432"
    }
    
    # 3. Define the Test Event
    event = {
        "httpMethod": "POST",
        "body": json.dumps({
            "id": "sajna_01", 
            "name": "Sajna Taxi", 
            "image": VALID_PNG
        })
    }
    
    # 4. Run the Handler
    response = main(event, None)
    
    # 5. Professional Debugging: If it fails, we want to see the error message in the logs
    if response['statusCode'] != 200:
        print(f"FAILED RESPONSE BODY: {response['body']}")
        
    assert response['statusCode'] == 200
    
    # Verify the response content
    body = json.loads(response['body'])
    assert body['id'] == "sajna_01"