Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "build_pydantic_core_android.sh"
if (!(Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "wsl.exe not found. Build Android pydantic-core wheels in WSL2/Linux/macOS, or use the included GitHub Actions workflow."
}

# Pass all arguments through to the WSL bash script. The source tree must be reachable from WSL,
# which is true for normal Windows drives mounted as /mnt/c/....
wsl.exe bash (wslpath -a "$script") @Args
