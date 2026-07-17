# Android Wrapper v4.20 notes

Fixes the CN post-download loop introduced by treating honoka/SIF CN package versions as two-part NPPS4 versions.

Observed behavior in `sif_cn_full_log10.txt`:

- `/main.php/download/update` returned 200 repeatedly.
- The client downloaded only `99_0_1.zip` through `99_0_115.zip`, then restarted and repeated the same update pass.
- It never progressed to `/main.php/download/batch`, `/main.php/download/additional`, or `/main.php/download/getUrl`.

Root cause:

- honoka-chan's CN `PackageVersion` is `97.4.6`.
- v4.18/v4.19 kept the CN config at `97.4` and returned update item `version = "97.4"`.
- The CN client persisted/compared the exact three-part package version and therefore never considered the 99-package update complete.

Changes:

- Accept `major.minor.patch` in config version validation.
- Default CN `client_version` is now `97.4.6`.
- `cn_archive` compares and returns the exact raw CN version string for `/download/update`.
- Existing Android workspace configs using `backend = "cn_archive"` and `client_version = "97.4"` are migrated to `97.4.6` without overwriting other profile settings.
- Kotlin quick-profile buttons now write `97.4.6` for CN archive configs.

After installing this version, clear the CN client's half-downloaded cache once and test from scratch.
