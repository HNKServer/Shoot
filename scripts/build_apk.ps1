Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (!(Test-Path ".\gradlew.bat")) {
    $gradle = Get-Command gradle -ErrorAction SilentlyContinue
    if ($null -eq $gradle) {
        throw "Gradle is not installed and gradlew.bat is missing. Install Android Studio/Gradle, then run: gradle wrapper --gradle-version 8.10.2"
    }
    gradle wrapper --gradle-version 8.10.2
}
.\gradlew.bat --no-daemon assembleDebug
Write-Host "APK: $((Get-Location).Path)\app\build\outputs\apk\debug\app-debug.apk"
