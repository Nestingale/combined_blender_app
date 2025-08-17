import os
import logging
import aiohttp
import requests
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class ImageDownloadError(Exception):
    """Custom exception for image download errors"""
    pass

class FileHandlingService:
    """
    Service for handling file operations, particularly downloading images from public URLs.
    This service is separate from S3Service to handle operations that don't require AWS credentials.
    """
    
    @staticmethod
    async def download_image_from_url_async(url: str, file_path: str, timeout: int = 60) -> bool:
        """
        Asynchronously download an image from a public URL to a local file path.
        
        Args:
            url (str): The public URL of the image to download
            file_path (str): The local path where the image should be saved
            timeout (int): Timeout in seconds for the HTTP request
            
        Returns:
            bool: True if the download was successful
            
        Raises:
            ImageDownloadError: If the download fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Download the file asynchronously
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        raise ImageDownloadError(f"Failed to download from {url}, status code: {response.status}")
                    
                    # Write the file in chunks
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
            
            logger.info(f"Successfully downloaded image from {url} to {file_path}")
            return True
            
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error while downloading from {url}: {str(e)}")
            raise ImageDownloadError(f"HTTP error: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout while downloading from {url}")
            raise ImageDownloadError(f"Download timeout after {timeout} seconds")
        except Exception as e:
            logger.error(f"Failed to download from {url} to {file_path}: {str(e)}")
            raise ImageDownloadError(f"Download failed: {str(e)}")
    
    @staticmethod
    def download_image_from_url(url: str, file_path: str, timeout: int = 60) -> bool:
        """
        Synchronously download an image from a public URL to a local file path.
        
        Args:
            url (str): The public URL of the image to download
            file_path (str): The local path where the image should be saved
            timeout (int): Timeout in seconds for the HTTP request
            
        Returns:
            bool: True if the download was successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Download the file
            response = requests.get(url, stream=True, timeout=timeout)
            if response.status_code != 200:
                logger.error(f"Failed to download from {url}, status code: {response.status_code}")
                return False
                
            # Write the file in chunks
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Successfully downloaded image from {url} to {file_path}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"HTTP error while downloading from {url}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to download from {url} to {file_path}: {str(e)}")
            return False
    
    @staticmethod
    def ensure_directory_exists(directory_path: str) -> bool:
        """
        Ensure that a directory exists, creating it if necessary.
        
        Args:
            directory_path (str): Path to the directory
            
        Returns:
            bool: True if the directory exists or was created successfully
        """
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {str(e)}")
            return False
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            bool: True if the file exists
        """
        return os.path.isfile(file_path)
