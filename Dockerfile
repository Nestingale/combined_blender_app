FROM registry.infra.nestingale.com/nestingale/blender-runtime:4.4.0-py3.10

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BLENDER_PATH=/usr/local/bin/blender

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN BLENDER_PYTHON="$(find /opt/blender -type f -path '*/python/bin/python3.*' | head -n 1)" \
    && "$BLENDER_PYTHON" -m ensurepip \
    && "$BLENDER_PYTHON" -m pip install --no-cache-dir Pillow numpy

COPY app ./app

RUN mkdir -p \
    /app/app/scripts/photo_realistic_view/generated_files \
    /app/app/scripts/product_2d_to_3d/input \
    /app/app/scripts/product_replacement/generated_files \
    /app/app/scripts/usdz_to_glb_conversion

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]