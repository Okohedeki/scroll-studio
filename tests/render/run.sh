#!/usr/bin/env bash
# The render tests, run inside the pinned image (see tests/render/README.md for the docker command; CI runs this too):
#   mcr.microsoft.com/playwright/python:v1.58.0-noble
# The image has Chromium, its fonts and Python, but neither the playwright package, Node nor the libraries OpenCV wants,
# so they are added here. The Python package must be the same version as the browsers baked into the image.
#   bash tests/render/run.sh -k style-bauhaus               extra arguments go to pytest
set -euo pipefail
cd "$(dirname "$0")/../.."
export SS_RENDER=1 DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1
PLAYWRIGHT=1.58.0        # = the image tag

apt-get update -qq
apt-get install -y -qq --no-install-recommends nodejs npm libgl1 libglib2.0-0t64 > /dev/null
pip install -q "playwright==$PLAYWRIGHT"
pip install -q -e ".[dev]"
npm ci --no-audit --no-fund --loglevel=error
python -m pytest tests/render -q -p no:cacheprovider -n "${RENDER_WORKERS:-auto}" --dist loadgroup "$@"
