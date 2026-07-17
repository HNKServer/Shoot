# NPPS4 Android Wrapper v3.0 notes

- Restores `targetSdk 30` and keeps `MANAGE_EXTERNAL_STORAGE`, so Android 11+ can grant All files access from the special access page.
- Removes the misleading targetSdk=29 legacy-storage assumption.
- Adds Gradle/Kotlin daemon stability settings: `kotlin.compiler.execution.strategy=in-process`.
- Keeps CDN ZIPs read-only. The wrapper never edits ordinary ZIP packages, and does not rewrite `99_0_115.zip`.
- Master DBs are not player progress databases. They are read-only client/game master databases required by NPPS4. Player/account/progress DB is still created by NPPS4 automatically.
- Adds quick path reset buttons for `/storage/emulated/0/NPPS4` and `/storage/emulated/0/LoveLive/list_CN_Android`.
