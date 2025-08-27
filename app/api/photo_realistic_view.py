from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import json
import os
import logging
from app.core.config import get_settings
from app.services.s3_service import S3Service, S3ServiceError
from app.services.sqs_service import SQSService
from app.services.blender_service import process_blender_request_async, BlenderError, OutputFile
from app.services.file_handling_service import FileHandlingService, ImageDownloadError
from app.utils.file_utils import cleanup_processing_files

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize services
s3_service = S3Service(default_bucket_name=settings.S3_BUCKET_NAME, region_name=settings.AWS_REGION)
sqs_service = SQSService(settings.SQS_QUEUE_URL)

class PhotoRealisticViewRequest(BaseModel):
    template_id: str = Field(..., description="Unique identifier for the template")
    glb_image_key: str = Field(..., description="S3 key for input GLB file or public URL")
    generated_2d_image_key: str = Field(..., description="S3 key for output 2D image")
    all_masks_key: str = Field(..., description="S3 key for all product masks")
    camera_info: Any = Field(..., description="Camera information for rendering")
    lighting_info: Any = Field(..., description="Lighting information for rendering")

    class Config:
        schema_extra = {
            "example": {
                "template_id": "template123",
                "glb_image_key": "inputs/scene.glb",
                "generated_2d_image_key": "outputs/render.png",
                "all_masks_key": "outputs/all_masks.png",
                "camera_info": {},
                "lighting_info": {},
            }
        }        

@router.post("/generatePhotoRealisticView", status_code=status.HTTP_200_OK)
async def generate_photo_realistic_view(
    request: PhotoRealisticViewRequest
):
    """
    Generate a photo-realistic view of a 3D model with the specified camera and lighting settings.
    Returns the S3 locations of the generated files.
    """
    try:
        logger.info(f"Processing request for template_id: {request.template_id}")

        # Define working directory and paths
        working_dir = os.path.join(settings.BLENDER_SCRIPTS_PATH, 'photo_realistic_view')
        script_path = os.path.join(working_dir, 'blender_script.py')
        output_dir = os.path.join(working_dir, 'generated_files')

        # Print all paths for debugging
        logger.info(f"Working directory: {working_dir}")
        logger.info(f"Script path: {script_path}")
        logger.info(f"Output directory: {output_dir}")

        # Create working directory if it doesn't exist
        os.makedirs(working_dir, exist_ok=True)
        os.makedirs(os.path.join(working_dir, 'input'), exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)
        
      
        # Download input GLB file from S3 or URL
        input_file_local_path = os.path.join(working_dir, 'input', os.path.basename(request.glb_image_key))
        logger.info(f"Downloading input file: {request.glb_image_key} to {input_file_local_path}")

        # Check if the input is a URL or an S3 key
        if request.glb_image_key.startswith(('http://', 'https://')):
            # It's a URL, use FileHandlingService
            try:
                await FileHandlingService.download_image_from_url_async(
                    url=request.glb_image_key, 
                    file_path=input_file_local_path
                )
                logger.info(f"Successfully downloaded input file from URL")
            except ImageDownloadError as e:
                logger.error(f"Failed to download file from URL: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download input file: {str(e)}"
                )
        else:
            # It's an S3 key, use S3Service
            try:
                await s3_service.download_file_async(request.glb_image_key, input_file_local_path, bucket_name=settings.S3_BUCKET_NAME)
                logger.info(f"Successfully downloaded input file from S3")
            except S3ServiceError as e:
                logger.error(f"Failed to download file from S3: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download input file: {str(e)}"
                )


        # Configure output files
        output_files = [
            OutputFile(
                local_path=os.path.join(output_dir, 'room_render.png'),
                s3_key=request.generated_2d_image_key,
                file_type='png'
            ),
            OutputFile(
                local_path=os.path.join(output_dir, 'mask_all_products.png'),
                s3_key=request.all_masks_key,
                file_type='png'
            ),
        ]

        # Construct Blender command as a list of arguments
        blender_path = settings.BLENDER_PATH if hasattr(settings, 'BLENDER_PATH') else 'blender'

        blender_command = [
            "/usr/local/bin/blender",
            "--background",
            "--python", script_path,
            "--",  # Argument separator
            input_file_local_path,  # Local path to input file instead of S3 key
            "-d", output_dir,  # Working directory
            f"--generate-mask",
             f"--combined_mask_only",
            f"--camera-json", json.dumps(request.camera_info),
            f"--lighting-json", json.dumps(request.lighting_info),
            f"--use-environment-map", json.dumps("studio.exr"),
            f"--use-existing-camera",
        ]

        # Process the request with the new approach
        processed_files = await process_blender_request_async(
            working_dir=working_dir,
            blender_command=blender_command,
            output_files=output_files
        )
        
        # Upload output files to S3
        uploaded_files = []
        for file in processed_files:
            try:
                await s3_service.upload_file_async(
                    file.local_path,
                    file.s3_key,
                    bucket_name=settings.S3_BUCKET_NAME
                )
                uploaded_files.append(file)
                logger.info(f"Uploaded {file.local_path} to {file.s3_key}")
            except S3ServiceError as e:
                logger.error(f"Failed to upload output file {file.local_path}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload output file: {str(e)}"
                )

        return {
            "status": "completed",
            "template_id": request.template_id,
            "files": [
                {
                    "type": file.file_type,
                    "s3_key": file.s3_key
                }
                for file in uploaded_files
            ]
        }

    except BlenderError as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    # finally:
    #     # Clean up the downloaded input file and local output files
    #     await cleanup_processing_files(
    #         input_files=input_file_local_path, 
    #         output_files=output_files,
    #         working_dir=working_dir
    #     )

# The cleanup_files function is now in utils.file_utils module
