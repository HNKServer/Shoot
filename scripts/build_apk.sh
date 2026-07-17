#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x ./gradlew ]; then
  if ! command -v gradle >/dev/null 2>&1; then
    echo "Gradle is not installed and ./gradlew is missing." >&2
    echo "Install Android Studio/Gradle, then run: gradle wrapper --gradle-version 8.10.2" >&2
    exit 1
  fi
  gradle wrapper --gradle-version 8.10.2
fi
./gradlew --no-daemon assembleDebug
printf '\nAPK: %s\n' "$(pwd)/app/build/outputs/apk/debug/app-debug.apk"
