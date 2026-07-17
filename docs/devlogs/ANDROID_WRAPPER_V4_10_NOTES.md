# Android Wrapper v4.10

Fixes Kotlin compile errors introduced in v4.9:

- `ConfigEditorActivity`: use `this@ConfigEditorActivity` inside the nested `LinearLayout.apply` block when calling `PythonBridge.reloadEditableData` and `CrashReporter.append`.
- `MainActivity`: add the missing `startStatusPolling` / `stopStatusPolling` methods for the auto-refresh feature.
- `MainActivity`: reset `statusUpdating` after a poll completes, otherwise the first poll could block later status refreshes.
