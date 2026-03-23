import mimetypes

from .boto_client import s3_client
from ..core.config import config


def _guess_content_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


def create_presigned_url_post_operation(
    bucket_name: str, object_name: str, filename: str, expiration: int = 600
) -> dict:
    content_type = _guess_content_type(filename)
    response = s3_client.generate_presigned_post(
        Bucket=bucket_name,
        Key=object_name,
        Fields={"Content-Type": content_type},
        Conditions=[
            ["content-length-range", 0, config.max_file_size],
            {"Content-Type": content_type},
        ],
        ExpiresIn=expiration,
    )

    return response


# Generate a presigned URL for the S3 object
def create_presigned_url_get_operation(bucket_name, object_name, expiration=600):
    """code taken from: https://docs.aws.amazon.com/boto3/latest/guide/s3-examples.html"""
    response = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": object_name},
        ExpiresIn=expiration,
    )

    # The response contains the presigned URL
    return response


def create_presigned_url_put_operation(
    bucket_name: str, object_name: str, filename: str, expiration: int = 600
):
    content_type = _guess_content_type(filename)
    response = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket_name,
            "Key": object_name,
            "ContentType": content_type,
        },
        ExpiresIn=expiration,
    )

    return response


def delete_object(bucket_name: str, object_name: str) -> None:
    s3_client.delete_object(Bucket=bucket_name, Key=object_name)


def delete_objects_by_prefix(bucket_name: str, prefix: str) -> None:
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        contents = page.get("Contents", [])
        if not contents:
            continue
        s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
        )
