import os
import json
import asyncio
import subprocess
from typing import Dict, Any, List
import logging
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

@dataclass
class OutputFile:
    local_path: str
    s3_key: str
    file_type: str

class BlenderError(Exception):
    """Custom exception for Blender-related errors"""
    pass

async def process_blender_request_async(
    working_dir: str,
    blender_command: List[str],
    output_files: List[OutputFile]
) -> List[OutputFile]:
    """
    Process a Blender request using a pre-constructed blender command.
    This function runs Blender to generate output files but doesn't handle S3 uploads.
    The API handlers are responsible for uploading the generated files to S3.
    
    Args:
        working_dir: Directory where processing will take place
        blender_command: Pre-constructed Blender command as a list of arguments
        output_files: List of output file configurations
    
    Returns:
        List of processed output files that were successfully generated.
    """
    try:
        # Validate parameters
        if not working_dir:
            raise ValueError("Working directory is required")
        if not blender_command:
            raise ValueError("Blender command is required")
        if not output_files:
            raise ValueError("At least one output file configuration is required")

        # Create working directory if it doesn't exist
        os.makedirs(working_dir, exist_ok=True)
        
        logger.info(f"Running Blender command: {' '.join(blender_command)}")

        # Execute Blender command with retry logic
        for attempt in range(3):
            try:
                # Set a timeout that is slightly less than typical cloud service timeouts
                result = subprocess.run(
                    blender_command,
                    check=True,
                    timeout=3500  # 58.3 minutes in seconds
                )
                
                logger.info(f"Blender processing complete")
                break
            
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else f"Process failed with code {e.returncode}"
                logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise BlenderError(f"All retry attempts failed: {error_msg}")
            
            except subprocess.TimeoutExpired as e:
                error_msg = f"Blender process timed out after {e.timeout} seconds"
                logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise BlenderError(f"All retry attempts failed: {error_msg}")
            
            except Exception as e:
                if attempt == 2:
                    raise BlenderError(f"Failed to execute Blender: {str(e)}")
                await asyncio.sleep(2 ** attempt)

        # Check if output files were generated but don't upload them
        processed_files = []
        for output_file in output_files:
            if os.path.exists(output_file.local_path):
                processed_files.append(output_file)
                logger.info(f"Generated output file {output_file.local_path}")
            else:
                logger.warning(f"Output file {output_file.local_path} does not exist.")

        return processed_files

    except ValueError as e:
        logger.error(f"Invalid parameters for Blender request: {str(e)}")
        raise BlenderError(str(e))
    except Exception as e:
        logger.error(f"Error processing Blender request: {str(e)}", exc_info=True)
        raise BlenderError(str(e))