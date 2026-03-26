import json
import os
import urllib.request
import urllib.error

import boto3

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

API_BASE_URL = os.environ["API_BASE_URL"]
API_KEY_SECRET_ARN = os.environ["API_KEY_SECRET_ARN"]

# Fetch API key once at Lambda initialization (cached across invocations)
_api_key_cache = None


def get_api_key():
    global _api_key_cache
    if _api_key_cache is None:
        response = secrets_client.get_secret_value(SecretId=API_KEY_SECRET_ARN)
        _api_key_cache = response["SecretString"]
    return _api_key_cache


def lambda_handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        size = record["s3"]["object"]["size"]

        # Key format is "{project_id}/{document_id}"
        parts = key.split("/")
        if len(parts) != 2:
            print(f"Skipping unexpected key format: {key}")
            continue

        document_id = parts[1]

        # Get content type from S3 object metadata
        head = s3_client.head_object(Bucket=bucket, Key=key)
        content_type = head.get("ContentType", "application/octet-stream")

        # Call the backend API to confirm the upload
        payload = json.dumps(
            {
                "document_id": document_id,
                "size": size,
                "content_type": content_type,
            }
        ).encode("utf-8")

        url = f"{API_BASE_URL}/internal/documents/upload-confirm"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": get_api_key(),
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                print(f"Confirmed upload for document {document_id}: {body}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"API error for document {document_id}: {e.code} {error_body}")
            raise
        except urllib.error.URLError as e:
            # URLError usually has no response body; log the reason for TLS/DNS/connect issues.
            print(
                "Connection error for document "
                f"{document_id}: reason={e.reason!r}, url={url}"
            )
            raise

    return {"statusCode": 200}
