Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$wheels = Get-ChildItem "app/src/main/python/wheels" -Filter "pydantic_core-*-cp313-*-android_*.whl" -ErrorAction SilentlyContinue
if ($null -eq $wheels -or $wheels.Count -eq 0) {
    throw "Missing cp313 Android pydantic-core wheel. Run tools\pydantic_core_android\build_pydantic_core_android.ps1 first."
}
if (!(Select-String -Path "app/src/main/python/constraints-android.txt" -Pattern "^pydantic-core==" -Quiet)) {
    throw "constraints-android.txt has no pydantic-core pin. Run tools\pydantic_core_android\build_pydantic_core_android.ps1 first."
}
& (Join-Path $PSScriptRoot "build_apk.ps1")
