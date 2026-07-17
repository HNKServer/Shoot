param(
  [string]$Destination = ".\sif-gl-archive",
  [string]$Server = "https://ll.sif.moe/npps4_dlapi"
)
$ErrorActionPreference = "Stop"
$work = Join-Path $PSScriptRoot "official-npps4-dlapi-tools"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$raw = "https://raw.githubusercontent.com/DarkEnergyProcessor/NPPS4-DLAPI/master"
foreach ($name in @("clone.py", "update_v1.1.py", "update_v1.2.py", "release_info.json")) {
  Invoke-WebRequest "$raw/$name" -OutFile (Join-Path $work $name)
}
python -m pip install --upgrade natsort "https://github.com/DarkEnergyProcessor/honky-py/releases/download/0.2.0/honkypy-0.2.0-py3-none-any.whl"
python (Join-Path $work "clone.py") $Destination $Server --no-ios
python (Join-Path $work "update_v1.1.py") $Destination
python (Join-Path $work "update_v1.2.py") $Destination
Write-Host "Android mirror ready: $Destination"
