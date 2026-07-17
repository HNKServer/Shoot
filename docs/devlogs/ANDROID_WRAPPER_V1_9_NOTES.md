# NPPS4 Android Wrapper v1.9

Fixes a Kotlin compile error in `MainActivity.kt`:

```text
Unresolved reference 'singleLine'
```

The `TextInputEditText` setup now calls the Java method `setSingleLine(true)` instead of the unresolved Kotlin property assignment `singleLine = true`.

No Python, Chaquopy, NPPS4, backup, or path-mapping behavior was changed from v1.8.
