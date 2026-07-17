# Android Wrapper v4.22 - CN one-pass download migration

This build stops treating CN as a JP/GL two-phase download flow.

Changes:
- Preserve package_type in CN /download/update package_list entries.
- For cn_archive, use the client's package_list to return the referenced archive packages during /download/update, so first-run can download the real data packages in one pass instead of only 99_0_*.zip.
- Keep honoka's 99_0_* update behavior when external_version differs from 97.4.6.
- Prefer an operator-provided archive 99_0_115.zip over the bundled fallback override; the bundled override is now only a fallback if the mirror lacks that file.

Rationale:
Logcat v4.21 shows the client downloaded 99_0_1.zip..99_0_115.zip once, then on restart /download/update and /download/event both returned empty and libGame crashed with the native message corresponding to "download list is empty!". The earlier code had discarded package_type and ignored package_list, preventing the actual one-pass data package download.
