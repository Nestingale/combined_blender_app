FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set the working directory
WORKDIR /app

# Build based on build arg (default: development)
ARG BUILD_ENV="development"
ENV BUILD_ENV=${BUILD_ENV}

# Install system dependencies needed for Blender scripts and production
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Log build environment
RUN echo "Building for environment: $BUILD_ENV"

# Copy the application code
COPY ./app ./app

# Copy the Blender scripts directory
# This ensures all Blender scripts are available in the container
COPY ./app/scripts /app/app/scripts

# Copy the environment variables example
COPY .env.example .env

# Create directories for working files and logs
RUN mkdir -p /app/app/scripts/photo_realistic_view/generated_files \
    /app/app/scripts/product_2d_to_3d/input \
    /app/app/scripts/product_replacement/generated_files \
    /app/app/scripts/usdz_to_glb_conversion \
    /app/logs \
    /app/working_data \
    && chmod 777 /app/logs /app/working_data

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using Uvicorn with production settings
# Using 4 workers for production workload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
