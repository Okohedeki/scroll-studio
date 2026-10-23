# The sandbox the GPU tests run in: a GitHub Actions runner that takes ONE job and is then thrown away, with the GPU,
# Blender, ComfyUI (pinned to the versions the engine is tested against) and torch inside. Nothing on the host is
# visible to it except the model folders, mounted read-only by launch.ps1. See README.md for the security model.
#
#   docker build -t scroll-studio-gpu-runner ci/gpu-runner
FROM ubuntu:24.04

ARG RUNNER_VERSION=2.338.0
ARG RUNNER_SHA256=af4b794c1bc41d73d40535e3fe092a39f9679cd8d965954c2aca25a05ca41d32
ARG BLENDER_VERSION=4.2.23
ARG BLENDER_SHA256=bea0eb3146be13eae6225409a117b215184f41b7f79e799f97cb3abb8f6dc404
ARG TORCH_VERSION=2.13.0
ARG TORCH_INDEX=https://download.pytorch.org/whl/cu130
ARG COMFY_SHA=f2a419eb5c107f422951e9f6afc9caf8ffe03f66
ARG FLORENCE2_SHA=9ece3de914214c5f581d725167bc9d0eeb0d1120
ARG LTXVIDEO_SHA=61ee82b23b18b6d7665c665bef47dbc270215f7d
ARG SEEDVR2_SHA=4490bd1f482e026674543386bb2a4d176da245b9
ARG SAM2_SHA=0c35fff5f382803e2310103357b5e985f5437f32

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 \
    NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-dev build-essential git curl ca-certificates jq xz-utils ffmpeg \
      libgl1 libegl1 libglib2.0-0 libsm6 libxext6 libxi6 libxrender1 libxkbcommon0 libxfixes3 libxxf86vm1 \
      libicu74 libkrb5-3 liblttng-ust1t64 libssl3t64 zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Blender (Cycles renders of products and blockouts), checked against its published checksum
RUN curl -fsSLo /tmp/blender.tar.xz "https://download.blender.org/release/Blender4.2/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    && echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
    && mkdir /opt/blender && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/blender.tar.xz

# One Python for the engine and ComfyUI, with the CUDA build of torch the host's ComfyUI uses
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install "torch==${TORCH_VERSION}" torchvision torchaudio --index-url "${TORCH_INDEX}"
ENV PATH=/opt/venv/bin:$PATH

# ComfyUI and the third-party nodes the engine uses, pinned. The engine's own nodes come from the checkout in each job.
RUN git clone https://github.com/comfyanonymous/ComfyUI /opt/comfy && git -C /opt/comfy checkout --detach "${COMFY_SHA}" \
    && pip install -r /opt/comfy/requirements.txt \
    && cd /opt/comfy/custom_nodes \
    && git clone https://github.com/kijai/ComfyUI-Florence2 && git -C ComfyUI-Florence2 checkout --detach "${FLORENCE2_SHA}" \
    && git clone https://github.com/Lightricks/ComfyUI-LTXVideo && git -C ComfyUI-LTXVideo checkout --detach "${LTXVIDEO_SHA}" \
    && git clone https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler && git -C ComfyUI-SeedVR2_VideoUpscaler checkout --detach "${SEEDVR2_SHA}" \
    && git clone https://github.com/kijai/ComfyUI-segment-anything-2 && git -C ComfyUI-segment-anything-2 checkout --detach "${SAM2_SHA}" \
    && for d in */; do if [ -f "$d/requirements.txt" ]; then pip install -r "$d/requirements.txt"; fi; done \
    && rm -rf /opt/comfy/models
COPY extra_model_paths.yaml /opt/comfy/extra_model_paths.yaml

# The Actions runner, checked against the checksum in its release notes
RUN useradd --create-home --uid 1001 --shell /bin/bash runner \
    && mkdir /home/runner/actions-runner && cd /home/runner/actions-runner \
    && curl -fsSLo runner.tar.gz "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    && echo "${RUNNER_SHA256}  runner.tar.gz" | sha256sum -c - \
    && tar -xzf runner.tar.gz && rm runner.tar.gz \
    && mkdir -p /opt/comfy/output /opt/comfy/input /opt/comfy/temp /opt/comfy/user /home/runner/hf \
    && chown -R runner:runner /home/runner /opt/comfy /opt/venv
COPY --chown=root:root --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

# What the engine reads (engine/config.py): Blender, ComfyUI, models. Hugging Face reads the read-only cache offline.
ENV BLENDER=/opt/blender/blender COMFY_URL=http://127.0.0.1:8188 COMFY_DIR=/opt/comfy STUDIO_MODELS=/models \
    HF_HOME=/home/runner/hf HF_HUB_CACHE=/models/hf/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 SS_GPU=1

USER runner
WORKDIR /home/runner/actions-runner
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
