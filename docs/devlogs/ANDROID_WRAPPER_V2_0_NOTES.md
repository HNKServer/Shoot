# NPPS4 Android Wrapper v2.0 crash diagnostics / safe startup

This build changes startup behavior to make crashes diagnosable:

- The app no longer starts Chaquopy/Python automatically when MainActivity opens.
- Periodic health checks no longer import Python before the user starts the server.
- A global uncaught-exception handler records Java/Kotlin crashes to the app external files directory.
- Service startup failures are recorded and surfaced on the main screen.
- The “Create public directory template” action is pure Kotlin and does not load Python.
- A new “Initialize Python workspace / self-check” button can be used to test Python explicitly.

If the app still exits immediately, collect the full text logcat filtered by AndroidRuntime and the package name, not a screenshot of general ViewRoot logs.
