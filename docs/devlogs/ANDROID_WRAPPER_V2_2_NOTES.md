# Android Wrapper v2.2

Fixes the startup crash:

```text
IllegalArgumentException: The style on this component requires your app theme to be Theme.MaterialComponents
```

The previous theme used `Theme.Material3.DayNight.NoActionBar`. On some combinations of Material Components 1.12 and Android runtime, `MaterialCardView` still enforces a `Theme.MaterialComponents` parent and rejects the Material3 theme parent.

Changes:

- `Theme.NPPS4Wrapper` now inherits from `Theme.MaterialComponents.DayNight.NoActionBar`.
- Keeps the fixed `#1769FF` brand color.
- Keeps the no-action-bar layout and inset-aware custom top spacing.
- No Python, Chaquopy, path mapping, CDN, or backup logic changes.
