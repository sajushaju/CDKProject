import json
import os
import pytest
import boto3
import importlib  # Special tool to import "lambda" folder
from unittest.mock import patch, MagicMock
from moto import mock_aws

# --- FIX: We use importlib because "lambda" is a reserved keyword ---
handler_module = importlib.import_module("lambda.handler")
main = handler_module.main

@pytest.fixture
def aws_env():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
    os.environ["BUCKET_NAME"] = "test-bucket"

VALID_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="

@mock_aws
@patch('pg8000.native.Connection')
@patch('lambda.handler.get_secrets') # This string is okay, Python doesn't execute it as code
def test_create_item_and_upload_s3(mock_secrets, mock_conn, aws_env):
    s3 = boto3.client("s3", region_name="eu-central-1")
    s3.create_bucket(Bucket="test-bucket", CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'})
    mock_secrets.return_value = {"username": "u", "password": "p", "host": "h", "port": "5432"}
    
    event = {
        "httpMethod": "POST",
        "body": json.dumps({"id": "sajna_01", "name": "Sajna Taxi", "image": VALID_PNG})
    }
    response = main(event, None)
    assert response['statusCode'] == 200