#!/usr/bin/env bash
# Register as an ephemeral runner (one job, then GitHub removes it), forget the registration token, take the job, exit.
# The container is started with --rm, so everything the job wrote disappears with it.
set -euo pipefail
: "${RUNNER_TOKEN:?launch.ps1 passes a one-hour registration token}"
: "${RUNNER_REPO:=https://github.com/Okohedeki/scroll-studio}"
./config.sh --unattended --ephemeral --disableupdate --replace \
  --url "$RUNNER_REPO" --token "$RUNNER_TOKEN" \
  --name "gpu-sandbox-$(hostname)" --labels "gpu,sandbox" --work /home/runner/work
unset RUNNER_TOKEN
exec ./run.sh
