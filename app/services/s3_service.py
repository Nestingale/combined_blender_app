from botocore.exceptions import NoCredentialsError, ClientError
import boto3
import aioboto3
import os
import logging
from typing import List, Optional
import asyncio
from functools import partial

logger = logging.getLogger(__name__)

class S3ServiceError(Exception):
    """Custom exception for S3 service errors"""
    pass

class S3Service:
    def __init__(self, default_bucket_name: str = None, region_name: str = 'us-east-1'):
        self.default_bucket_name = default_bucket_name
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.session = aioboto3.Session()

    async def upload_file_async(self, file_name: str, object_name: Optional[str] = None, bucket_name: Optional[str] = None) -> bool:
        """
        Asynchronously upload a file to S3.
        """
        if object_name is None:
            object_name = os.path.basename(file_name)
            
        # Use provided bucket_name or fall back to default
        bucket = bucket_name or self.default_bucket_name
        if not bucket:
            raise S3ServiceError("No bucket name provided and no default bucket set")

        try:
            if not os.path.exists(file_name):
                raise FileNotFoundError(f"The file {file_name} was not found.")

            async with self.session.client('s3', region_name=self.region_name) as s3:
                await s3.upload_file(file_name, bucket, object_name)
            
            logger.info(f"Successfully uploaded {file_name} to {bucket}/{object_name}")
            return True

        except (FileNotFoundError, NoCredentialsError, ClientError) as e:
            logger.error(f"Failed to upload {file_name} to {bucket}/{object_name}: {str(e)}")
            raise S3ServiceError(f"Upload failed: {str(e)}")

    async def download_file_async(self, object_name: str, file_name: str, bucket_name: Optional[str] = None) -> bool:
        """
        Asynchronously download a file from S3.
        """
        # Use provided bucket_name or fall back to default
        bucket = bucket_name or self.default_bucket_name
        if not bucket:
            raise S3ServiceError("No bucket name provided and no default bucket set")
            
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(file_name), exist_ok=True)

            async with self.session.client('s3', region_name=self.region_name) as s3:
                await s3.download_file(bucket, object_name, file_name)

            logger.info(f"Successfully downloaded {object_name} from {bucket} to {file_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to download {object_name} from {bucket}: {str(e)}")
            raise S3ServiceError(f"Download failed: {str(e)}")

    async def list_files_async(self, prefix: str = '', bucket_name: Optional[str] = None) -> List[str]:
        """
        Asynchronously list files in an S3 bucket with the given prefix.
        """
        # Use provided bucket_name or fall back to default
        bucket = bucket_name or self.default_bucket_name
        if not bucket:
            raise S3ServiceError("No bucket name provided and no default bucket set")
            
        try:
            async with self.session.client('s3', region_name=self.region_name) as s3:
                response = await s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []

        except ClientError as e:
            logger.error(f"Failed to list files in {bucket}: {str(e)}")
            raise S3ServiceError(f"List operation failed: {str(e)}")

    # Synchronous methods for backward compatibility
    def upload_file(self, file_name: str, object_name: Optional[str] = None, bucket_name: Optional[str] = None) -> bool:
        """
        Synchronously upload a file to S3.
        """
        try:
            if object_name is None:
                object_name = os.path.basename(file_name)
                
            # Use provided bucket_name or fall back to default
            bucket = bucket_name or self.default_bucket_name
            if not bucket:
                raise S3ServiceError("No bucket name provided and no default bucket set")
                
            self.s3_client.upload_file(file_name, bucket, object_name)
            logger.info(f"Successfully uploaded {file_name} to {bucket}/{object_name}")
            return True
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            return False

    def download_file(self, object_name: str, file_name: str, bucket_name: Optional[str] = None) -> bool:
        """
        Synchronously download a file from S3.
        """
        try:
            # Use provided bucket_name or fall back to default
            bucket = bucket_name or self.default_bucket_name
            if not bucket:
                raise S3ServiceError("No bucket name provided and no default bucket set")
                
            os.makedirs(os.path.dirname(file_name), exist_ok=True)
            self.s3_client.download_file(bucket, object_name, file_name)
            logger.info(f"Successfully downloaded {object_name} to {file_name}")
            return True
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return False

    def list_files(self, prefix: str = '', bucket_name: Optional[str] = None) -> List[str]:
        """
        Synchronously list files in an S3 bucket with the given prefix.
        """
        try:
            # Use provided bucket_name or fall back to default
            bucket = bucket_name or self.default_bucket_name
            if not bucket:
                raise S3ServiceError("No bucket name provided and no default bucket set")
                
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except Exception as e:
            logger.error(f"List operation failed: {str(e)}")
            return []