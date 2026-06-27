import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional, Any
from backend.app.core.config import settings

class S3Storage:
    def __init__(self):
        # Configure connection retries and timeouts
        config = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=5
        )

        # For local development with MinIO, we pass endpoint_url.
        # For production with AWS S3, settings.S3_ENDPOINT_URL can be empty or None,
        # in which case boto3 defaults to AWS S3.
        endpoint_url = settings.S3_ENDPOINT_URL if "localhost" in settings.S3_ENDPOINT_URL or "minio" in settings.S3_ENDPOINT_URL else None

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=config
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def ensure_bucket_exists(self) -> None:
        """Create the bucket if it does not exist (primarily useful for local MinIO setup)."""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in ["404", "NoSuchBucket", "403"] or http_status == 404:
                # Create bucket
                try:
                    if settings.AWS_REGION == "us-east-1":
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION}
                        )
                    print(f"Successfully created missing bucket: {self.bucket_name}")
                except ClientError as ce:
                    print(f"Error creating bucket {self.bucket_name}: {ce}")
            else:
                print(f"Error verifying bucket {self.bucket_name}: {e}")

    def get_document_key_prefix(self, org_id: Any, document_id: Any, version_number: int) -> str:
        """Construct the standard folder structure: org_id/document_id/version_number/"""
        return f"{org_id}/{document_id}/{version_number}/"

    def upload_file(self, file_path: str, object_name: str) -> bool:
        """Upload a file to S3 storage."""
        try:
            self.ensure_bucket_exists()
            self.client.upload_file(file_path, self.bucket_name, object_name)
            return True
        except ClientError as e:
            print(f"Failed to upload file to S3: {e}")
            return False

    def upload_fileobj(self, fileobj: Any, object_name: str) -> bool:
        """Upload a file-like object to S3 storage."""
        try:
            self.ensure_bucket_exists()
            self.client.upload_fileobj(fileobj, self.bucket_name, object_name)
            return True
        except ClientError as e:
            print(f"Failed to upload fileobj to S3: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration: int = 300) -> Optional[str]:
        """Generate a pre-signed HMAC URL to retrieve a file from S3. Default TTL = 5 minutes."""
        try:
            response = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            print(f"Failed to generate presigned URL: {e}")
            return None


s3_storage = S3Storage()
