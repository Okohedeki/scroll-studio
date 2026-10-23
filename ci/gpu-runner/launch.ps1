<#
Runs the sandboxed GPU runner on this machine: one fresh container per job, deleted when the job ends.

  docker build -t scroll-studio-gpu-runner ci/gpu-runner     # once, and after the Dockerfile changes
  powershell -File ci/gpu-runner/launch.ps1                  # takes jobs until Ctrl+C
  powershell -File ci/gpu-runner/launch.ps1 -Once            # one job, then stop

The GitHub login stays on this machine: `gh` asks GitHub for a registration token (valid one hour, good only for
registering a runner) and the container gets that token alone. The container sees the GPU and the model folders
(read-only), runs as an unprivileged user with every Linux capability dropped, and cannot reach the Docker daemon or
any other folder on this machine. See README.md.
#>
param(
  [string]$Image = "scroll-studio-gpu-runner",
  [string]$Repo = "Okohedeki/scroll-studio",
  [string]$ComfyModels = "D:\ai\ComfyUI\models",
  [string]$ExtraModels = "E:\ai\models",
  [string]$HfCache = "D:\ai\hf",
  [string]$Memory = "40g",
  [int]$Cpus = 12,
  [switch]$Once
)
$ErrorActionPreference = "Stop"

docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) { throw "Image $Image not found: docker build -t $Image ci/gpu-runner" }

$mounts = @()
foreach ($m in @(@($ComfyModels, "/models/comfy"), @($ExtraModels, "/models/extra"), @($HfCache, "/models/hf"))) {
  if (Test-Path $m[0]) { $mounts += @("--mount", "type=bind,source=$($m[0]),target=$($m[1]),readonly") }
  else { Write-Warning "$($m[0]) not found: $($m[1]) will be empty in the sandbox" }
}

do {
  $token = gh api -X POST "repos/$Repo/actions/runners/registration-token" -q .token
  if (-not $token) { throw "could not get a registration token (gh auth status: you need admin on $Repo)" }
  Write-Host "$(Get-Date -Format s) waiting for a GPU job in a fresh sandbox"
  docker run --rm --name "ss-gpu-runner-$([guid]::NewGuid().ToString('N').Substring(0, 8))" `
    --gpus all `
    --cap-drop ALL --security-opt no-new-privileges `
    --pids-limit 4096 --memory $Memory --cpus $Cpus --shm-size 8g `
    --tmpfs /tmp:rw,size=16g `
    -e RUNNER_TOKEN=$token -e RUNNER_REPO="https://github.com/$Repo" `
    @mounts `
    $Image
  $token = $null
  Write-Host "$(Get-Date -Format s) job finished, sandbox deleted"
} while (-not $Once)
