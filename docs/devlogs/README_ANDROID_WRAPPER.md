# NPPS4 Android Wrapper

This is a source-level Android wrapper for `NPPS4-cn-compat-minimal-v10`.
It embeds NPPS4 through Chaquopy and provides a native Android control app.

## What this wrapper provides

- Foreground-service based NPPS4 runtime so Android is less likely to kill the server immediately.
- Server start/stop and TCP health detection.
- App-private portable server workspace under:
  `Android/data/moe.honoka.npps4wrapper/files/npps4`
- Direct public-path CN CDN mapping under:
  `/storage/emulated/0/NPPS4/list_CN_Android` for flat CN archive ZIPs, including `99_0_115.zip`.
- Direct public-path NPPS4-readable master DB mapping under:
  `/storage/emulated/0/NPPS4/db`.
- One-click server-state export/import as ZIP for backup/migration. This backs up account/progress/config data only and deliberately excludes the public CDN archives and master DB directory.
- Text editor for key data files:
  - `config.toml`
  - `npps4/server_data.json`
  - `external/login_bonus.py`

## Storage model

The server state remains in the app workspace so it can be backed up and migrated easily. Large CDN archives and master DB files are used directly from `/storage/emulated/0/NPPS4` so they are not duplicated inside the app workspace. On Android 11+, grant **All files access** if the app cannot read the public path.

## Build requirements

- Android Studio or Android SDK + Gradle
- JDK 17+
- Internet access during first build, because Gradle and Chaquopy pip dependencies are downloaded.
- NDK is handled by the Android Gradle Plugin/Chaquopy as needed.

## Build

Linux/macOS:

```bash
cd NPPS4-Android-Wrapper
./scripts/build_apk.sh
```

Windows PowerShell:

```powershell
cd NPPS4-Android-Wrapper
.\scripts\build_apk.ps1
```

Debug APK output:

```text
app/build/outputs/apk/debug/app-debug.apk
```

## First-run workflow on Android

1. Install APK.
2. Open the app and tap **创建目录模板**.
3. Put CN archives directly into:
   `/storage/emulated/0/NPPS4/list_CN_Android`
   Put the patched `99_0_115.zip` in this same folder.
4. Put NPPS4-readable master DB files under:
   `/storage/emulated/0/NPPS4/db`
5. Grant all-files access if needed.
6. Edit `config.toml` if needed.
7. Start the server.
8. Client should use `http://127.0.0.1:51376/` from the same Android device.

## Important limits

This is a wrapper/source project, not a fully tested release APK. The current environment used to generate it does not have Android Gradle/Chaquopy build tooling, so the APK was not compiled here.

The wrapper intentionally does not use honoka-chan's simplified account/gameplay behavior. It runs the NPPS4 v10 compatibility code and only adds Android lifecycle/storage management around it.


## Build troubleshooting

If Android Studio reports `Unable to load class 'org.gradle.util.VersionNumber'`, use Chaquopy 17.0.0 or pin the project to Gradle 8.x. This wrapper package uses Chaquopy 17.0.0 in the top-level `build.gradle`.

If `gradlew` or `gradlew.bat` is missing, open the project in Android Studio and let it sync with the IDE's Gradle, or run `gradle wrapper --gradle-version 8.13` with a locally installed Gradle to generate wrapper files.


## Python / Chaquopy build version

This project uses Chaquopy 17.0 and Android runtime Python 3.13. Chaquopy requires the host build Python to have the same major/minor version as the app runtime, so `app/build.gradle` contains:

```gradle
chaquopy {
    defaultConfig {
        version = "3.13"
        buildPython("py", "-3.13")
    }
}
```

On Windows this uses the Python launcher. If Android Studio still reports that Python 3.13 cannot be found, replace `buildPython("py", "-3.13")` with your full Python path, for example `buildPython("C:/Users/you/AppData/Local/Programs/Python/Python313/python.exe")`.


## Build dependency note

This package targets Chaquopy Python 3.13 because `pycryptodomex` has Android wheels for cp313 in Chaquopy's package index. Python 3.14 will fail at `installDebugPythonRequirements` with `No matching distribution found for pycryptodomex`. Install Python 3.13 side-by-side and keep Python 3.14 for desktop NPPS4 if desired.

## v2.2 theme runtime fix

If the app shows `The style on this component requires your app theme to be Theme.MaterialComponents`, use v2.2 or later. The app theme now uses `Theme.MaterialComponents.DayNight.NoActionBar` while keeping the fixed `#1769FF` blue color.


## v2.9 note

Android targetSdk is now 29 with requestLegacyExternalStorage enabled. Use the new “请求外部存储读写权限” button before reading `/storage/emulated/0/...` public paths. Ordinary CDN ZIPs are treated as read-only.


## v4.1 dependency profile

This package uses native Pydantic v2 on Android. The Pydantic v1 compatibility shim has been removed. Because Pydantic v2 requires the native `pydantic-core` extension, the Gradle pip configuration only accepts binary wheels. If Chaquopy cannot find an Android-compatible `pydantic-core` wheel automatically, place cp313 Android wheels in `app/src/main/python/wheels/` and rebuild.
## v4.5 restart note

If the server starts once, then fails after changing the port with `Endpoint achievement/unaccomplishList is already registered!`, use v4.5 or newer. The wrapper now clears NPPS4 import-time endpoint registries before every Start, so host/port changes no longer poison the live Chaquopy interpreter.



- v4.7: fixes CN `/main.php/login/authkey` 422 by allowing honoka-style authkey requests with only `dummy_token`.
- v4.8: strengthens CN `/main.php/login/authkey` parsing so non-standard `request_data` wrappers and camelCase/direct-form variants no longer become FastAPI 422.

- v4.16: accept CN object-shaped download/update package_list entries while keeping NPPS4 internal list[int] semantics.
