import os
import asyncio
import subprocess
from typing import List
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
    """Custom exception for Blender-related errors."""
    pass


async def process_blender_request_async(
    working_dir: str,
    blender_command: List[str],
    output_files: List[OutputFile]
) -> List[OutputFile]:
    """
    Run Blender and verify that every expected output file was actually generated.

    Blender may exit with code 0 even when a Python script executed inside Blender
    fails, so process success cannot be determined from the return code alone.

    The API handlers remain responsible for uploading the generated files to S3.
    """

    # Validate parameters
    if not working_dir:
        raise BlenderError("Working directory is required")

    if not blender_command:
        raise BlenderError("Blender command is required")

    if not output_files:
        raise BlenderError("At least one output file configuration is required")

    os.makedirs(working_dir, exist_ok=True)

    logger.info(f"Running Blender command: {' '.join(blender_command)}")

    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            #
            # IMPORTANT:
            # Remove outputs from previous requests/attempts before running Blender.
            #
            # Otherwise a failed render could appear successful because an old
            # room_render.png or mask_all_products.png still exists.
            #
            for output_file in output_files:
                if os.path.exists(output_file.local_path):
                    logger.info(
                        f"Removing stale output file before Blender run: "
                        f"{output_file.local_path}"
                    )

                    try:
                        os.remove(output_file.local_path)
                    except OSError as e:
                        raise BlenderError(
                            f"Could not remove stale output file "
                            f"{output_file.local_path}: {e}"
                        )

            logger.info(
                f"Starting Blender attempt {attempt}/{max_attempts}"
            )

            #
            # Do NOT capture stdout/stderr here.
            #
            # Leaving them attached to the process allows Blender's output to
            # continue appearing in kubectl logs, Loki, and Grafana.
            #
            result = subprocess.run(
                blender_command,
                timeout=3500
            )

            #
            # First check the actual Blender process return code.
            #
            if result.returncode != 0:
                raise BlenderError(
                    f"Blender exited with non-zero status "
                    f"{result.returncode}"
                )

            #
            # Blender can return 0 even if the Python script failed.
            # Therefore every expected output must also exist and be non-empty.
            #
            missing_outputs = []
            empty_outputs = []

            for output_file in output_files:
                if not os.path.exists(output_file.local_path):
                    missing_outputs.append(output_file.local_path)
                    continue

                if os.path.getsize(output_file.local_path) <= 0:
                    empty_outputs.append(output_file.local_path)

            if missing_outputs or empty_outputs:
                error_parts = []

                if missing_outputs:
                    error_parts.append(
                        "missing expected output(s): "
                        + ", ".join(missing_outputs)
                    )

                if empty_outputs:
                    error_parts.append(
                        "empty expected output(s): "
                        + ", ".join(empty_outputs)
                    )

                raise BlenderError(
                    "Blender did not produce valid output: "
                    + "; ".join(error_parts)
                )

            #
            # At this point:
            #
            #   Blender exited successfully
            #   AND
            #   every expected file exists
            #   AND
            #   every expected file is non-empty
            #
            logger.info(
                f"Blender processing complete on attempt "
                f"{attempt}/{max_attempts}"
            )

            for output_file in output_files:
                size = os.path.getsize(output_file.local_path)

                logger.info(
                    f"Generated output file "
                    f"{output_file.local_path} "
                    f"({size} bytes)"
                )

            return output_files

        except subprocess.TimeoutExpired as e:
            error_msg = (
                f"Blender process timed out after "
                f"{e.timeout} seconds"
            )

        except BlenderError as e:
            error_msg = str(e)

        except Exception as e:
            error_msg = f"Unexpected Blender execution error: {e}"

        logger.warning(
            f"Blender attempt {attempt}/{max_attempts} failed: "
            f"{error_msg}"
        )

        if attempt < max_attempts:
            delay = 2 ** (attempt - 1)

            logger.info(
                f"Retrying Blender in {delay} second(s)"
            )

            await asyncio.sleep(delay)

        else:
            logger.error(
                f"Blender processing failed after "
                f"{max_attempts} attempts: {error_msg}"
            )

            raise BlenderError(
                f"Blender processing failed after "
                f"{max_attempts} attempts: {error_msg}"
            )