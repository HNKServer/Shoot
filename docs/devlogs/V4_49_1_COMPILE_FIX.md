# v4.49.1 Android compile fix

Only fixes the Kotlin compilation regression in `FileOps.defaultConfig`:

- restores the missing local `root` variable derived from `PythonBridge.workDir(context)`;
- bumps Android wrapper versionCode to 432 and versionName to 0.4.31.1;
- does not change NPPS4 server behavior or the v4.49 CN feature fixes.
