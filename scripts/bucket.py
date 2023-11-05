import os
from minio import Minio

client = Minio(os.environ.get('S3_ENDPOINT'), access_key=os.environ.get('ACCESS_KEY'), secret_key=os.environ.get('SECRET_KEY'), session_token=None, secure=False, region=None, http_client=None, credentials=None)

client.make_bucket(os.environ.get("S3_BUCKET"))
