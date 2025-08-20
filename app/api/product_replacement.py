from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import json
import os
import logging
from app.core.config import get_settings
from app.core.monitoring import track_time, BLENDER_PROCESSING_TIME
from app.services.s3_service import S3Service, S3ServiceError
from app.services.sqs_service import SQSService
from app.services.blender_service import process_blender_request_async, BlenderError, OutputFile
from app.services.file_handling_service import FileHandlingService, ImageDownloadError
from app.utils.file_utils import cleanup_processing_files

settings = get_settings()
logger = logging.getLogger(__name__)

s3_service = S3Service(settings.S3_BUCKET_NAME, settings.AWS_REGION)
sqs_service = SQSService(settings.SQS_QUEUE_URL)
router = APIRouter()

class ProductReplacementRequest(BaseModel):
    product_sku_id: str = Field(..., description="Unique identifier for the product")
    glb_image_key: str = Field(..., description="S3 key for input GLB file or public URL")
    generated_2d_image_key: str = Field(..., description="S3 key for output 2D image")
    all_masks_key: str = Field(..., description="S3 key for all product masks")
    target_product_mask_key: str = Field(..., description="S3 key for target product mask")
    target_product_image_key: str = Field(..., description="S3 key for target product image")
    camera_info: Any = Field(..., description="Camera information for rendering")
    lighting_info: Any = Field(..., description="Lighting information for rendering")
    replace_product_data: Any = Field(..., description="Data for replacing the product in the scene")

    class Config:
        schema_extra = {
            "example": {
                "product_sku_id": "SKU123",
                "glb_image_key": "inputs/scene.glb",
                "generated_2d_image_key": "outputs/render.png",
                "all_masks_key": "outputs/all_masks.png",
                "target_product_mask_key": "outputs/target_mask.png",
                "target_product_image_key": "outputs/target_image.png",
                "camera_info": {},
                "lighting_info": {},
                "replace_product_data": {}
            }
        }

@router.post("/replaceProduct", status_code=status.HTTP_200_OK)
@track_time(BLENDER_PROCESSING_TIME, {"task_type": "product_replacement"})
async def replace_product(request: ProductReplacementRequest):
    """
    Replace a product in a 3D scene and generate a new render with masks.
    """
    try:
        logger.info(
            "Processing product replacement request",
            extra={
                "sku_id": request.product_sku_id
            }
        )

        # Define working directory and paths
        working_dir = os.path.join(settings.BLENDER_SCRIPTS_PATH, 'product_replacement')
        script_path = os.path.join(working_dir, 'blender_script.py')
        output_dir = os.path.join(working_dir, 'generated_files')

        # Print all paths for debugging
        logger.debug(f"Working directory: {working_dir}")
        logger.debug(f"Script path: {script_path}")
        logger.debug(f"Output directory: {output_dir}")

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
                await s3_service.download_file_async(request.glb_image_key, input_file_local_path)
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
            OutputFile(
                local_path=os.path.join(output_dir, f'mask_{request.product_sku_id}.png'),
                s3_key=request.target_product_mask_key,
                file_type='png'
            ),
            OutputFile(
                local_path=os.path.join(output_dir, f'individual_masked_{request.product_sku_id}.png'),
                s3_key=request.target_product_image_key,
                file_type='png'
            )
        ]

        # Process the request
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
            f"--camera-json", json.dumps(request.camera_info),
            f"--lighting-json", json.dumps(request.lighting_info),
            f"--use-environment-map", json.dumps("studio.exr"),
            f"--use-existing-camera",
            f"--replace-product", json.dumps(request.replace_product_data)
        ]

        # Process the request with the new approach
        processed_files = await process_blender_request_async(
            working_dir=working_dir,
            blender_command=blender_command,
            output_files=output_files
        )

        return {
            "status": "completed",
            "product_sku_id": request.product_sku_id,
            "files": [
                {
                    "type": file.file_type,
                    "s3_key": file.s3_key
                }
                for file in processed_files
            ]
        }

    except BlenderError as e:
        logger.error(f"Error processing replaceProduct request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )