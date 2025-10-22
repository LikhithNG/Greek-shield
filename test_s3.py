import os
from dotenv import load_dotenv
import boto3
from datetime import date

load_dotenv()

print("Testing S3 connection...")

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bucket = os.getenv('S3_BUCKET_NAME')

# Test upload
test_key = f"test/test_{date.today()}.txt"
s3.put_object(
    Bucket=bucket,
    Key=test_key,
    Body="Test file from Python!"
)

print(f"✅ Successfully uploaded to s3://{bucket}/{test_key}")
print("S3 connection working!")