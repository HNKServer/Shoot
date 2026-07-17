Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$WheelDir = Join-Path $RootDir "app\src\main\python\wheels"
$Constraints = Join-Path $RootDir "app\src\main\python\constraints-android.txt"
$IndexUrl = "https://pypi.flet.dev/pydantic-core"
$FileNames = @(
    "pydantic_core-2.33.2-cp313-cp313-android_24_arm64_v8a.whl",
    "pydantic_core-2.33.2-cp313-cp313-android_24_x86_64.whl"
)

New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

Write-Host "Reading $IndexUrl"
$page = (Invoke-WebRequest -Uri $IndexUrl -UseBasicParsing -TimeoutSec 60).Content
$baseUri = [System.Uri]::new($IndexUrl + "/")

foreach ($fileName in $FileNames) {
    $escaped = [Regex]::Escape($fileName)
    $match = [Regex]::Match($page, "href=[`"']([^`"']*$escaped[^`"']*)[`"']")
    if (-not $match.Success) {
        throw "Could not find $fileName in $IndexUrl"
    }

    $href = [System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value)
    $uri = [System.Uri]::new($baseUri, $href)
    $output = Join-Path $WheelDir $fileName
    Write-Host "Downloading $fileName"
    Invoke-WebRequest -Uri $uri.AbsoluteUri -OutFile $output -UseBasicParsing -TimeoutSec 300
    Write-Host "  -> $output"
}

@"
# Android/Chaquopy native Pydantic v2 pins.
# Generated/refreshed by tools/pydantic_core_android/fetch_flet_pydantic_core_wheels.ps1.
#
# Target runtime:
#   Chaquopy Python: 3.13
#   Android wheel tags: cp313-cp313-android_24_arm64_v8a and
#                       cp313-cp313-android_24_x86_64
pydantic==2.11.10
pydantic-core==2.33.2
"@ | Set-Content -Encoding UTF8 -Path $Constraints

Write-Host "Done. Wheels are in: $WheelDir"
Write-Host "Constraints refreshed: $Constraints"
