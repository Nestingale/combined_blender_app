FROM python:3.10-slim-bookworm

ARG BLENDER_VERSION=4.4.0
ARG BLENDER_ARCHIVE=blender-4.4.0-linux-x64.tar.xz

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BLENDER_PATH=/usr/local/bin/blender

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    xz-utils \
    libgl1 \
    libegl1 \
    libx11-6 \
    libxi6 \
    libxrender1 \
    libxfixes3 \
    libxkbcommon0 \
    libsm6 \
    libice6 \
    libxext6 \
    libxxf86vm1 \
    libwayland-client0 \
    libwayland-egl1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL \
    "https://download.blender.org/release/Blender4.4/${BLENDER_ARCHIVE}" \
    -o /tmp/blender.tar.xz \
    && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz \
        --strip-components=1 \
        -C /opt/blender \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && rm /tmp/blender.tar.xz

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

RUN mkdir -p \
    /app/app/scripts/photo_realistic_view/generated_files \
    /app/app/scripts/product_2d_to_3d/input \
    /app/app/scripts/product_replacement/generated_files \
    /app/app/scripts/usdz_to_glb_conversion

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]