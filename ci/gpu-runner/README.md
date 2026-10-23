# The sandboxed GPU runner

The GPU tests (`tests/gpu/`, `.github/workflows/gpu.yml`) need a 24 GB GPU, which GitHub's runners do not have. Until
dedicated compute exists ([#32](https://github.com/Okohedeki/scroll-studio/issues/32)) they run on the maintainer's
machine, in a sandbox built so that no code from anyone else can reach that machine.

## Who can run code on it

- **Only the maintainer starts GPU jobs.** `gpu.yml` runs on a manual dispatch by the maintainer or on the nightly
  schedule (which runs `main`), and never on pull requests. Its job checks the repository and the actor.
- **Pull requests from forks cannot start any workflow** without the maintainer's approval (repository setting: approval
  required for all outside contributors). A pull request that adds or edits a workflow could otherwise ask for this
  runner by its labels: **never approve a workflow run for a pull request that changes `.github/`.**
- **`main` is protected**: changes arrive only through pull requests with the `tests` check green.

## What a job can reach

- **One job, one container.** The runner registers as *ephemeral*: GitHub gives it exactly one job and then removes it.
  The container is started with `--rm`, so whatever the job wrote is deleted when it ends. The next job starts from the
  clean image.
- **Not this machine.** The container runs as an unprivileged user with every Linux capability dropped and
  `no-new-privileges`, with limits on memory, CPUs and processes. It has no Docker socket and no host folder except the
  model folders, mounted **read-only**: `D:\ai\ComfyUI\models`, `E:\ai\models` and the Hugging Face cache `D:\ai\hf`.
- **Not the GitHub login.** `launch.ps1` uses the host's `gh` to ask GitHub for a registration token (valid one hour,
  good only for registering a runner); the container receives that and nothing else, and drops it once registered.
  The job's own `GITHUB_TOKEN` is read-only (repository default).
- **The network**: outbound internet, which the runner needs to talk to GitHub. Models are read offline from the
  read-only mounts (`HF_HUB_OFFLINE=1`); ComfyUI listens on the container's own loopback only.

## Use it

```powershell
docker build -t scroll-studio-gpu-runner ci/gpu-runner      # once, and after this folder changes
powershell -File ci/gpu-runner/launch.ps1                   # takes jobs until Ctrl+C (-Once: one job)
gh workflow run gpu                                          # start the GPU tests (maintainer only)
```

The runner is only online while `launch.ps1` runs; a scheduled job waits for it (up to a day). Don't run it while
building a heavy site: the GPU is shared.

## Pinned versions

Everything in the image is pinned in the `Dockerfile`: Ubuntu 24.04, torch 2.13 (CUDA 13), Blender 4.2 LTS and the
Actions runner (both checked against published SHA-256 checksums), ComfyUI and the four third-party nodes at the
commits the engine is tested against. The engine's own ComfyUI nodes come from the checkout in each job.

## Goldens

GPU output is repeatable on one machine but not bit-identical across drivers, so tests compare pictures with the
goldens in `tests/gpu/golden/` by structure (SSIM). To record a new golden, run the tests in the image with
`SS_GPU_RECORD=1`, look at the pictures, and commit them in a pull request.
