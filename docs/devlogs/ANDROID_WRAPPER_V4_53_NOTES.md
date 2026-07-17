# Android Wrapper v4.53

This build fixes the remaining CN home-banner and Museum regressions without
changing the retained 97.4.6 update version or modifying 99_0_113/114/115.

- Front home carousel: data transfer first, followed by the same type-1
  scouting pages exposed by `secretbox/all`.
- Back home carousel: one type-2 official manga WebView banner.
- Custom WebView images are injected into an existing normal full-data package,
  not a synthetic 99 update package.
- The merged Museum DB replaces the original entry inside its normal full-data
  package. The original archive remains read-only; a cached patched copy is
  served under the same package URL and package ID with the corrected size.
- The final WW Museum `base.lua` is re-encrypted for the CN Honky contract and
  delivered through the same content overlay, enabling missing `.flsh` assets
  to use the normal micro-download/GL-overlay path.
- `museum/info` returns only the original 16 IDs until the patched Museum
  package has actually been served, preventing a 1360-ID response from crashing
  a client that still has the 16-row local catalogue.
- Old NPPS4-generated 99_0_116/117 entries are removed from existing config;
  unrelated operator-provided extra packages are preserved.

## Upgrade/test behavior

An already initialized CN client will not request the modified normal packages
again. On such a client v4.53 keeps `museum/info` on the original 16 IDs so the
old local catalogue does not crash. To test the new thumbnails and 1360-entry
catalogue, clear only the CN game's client data (not the Wrapper workspace) and
run the ordinary first-time full download once.

The diagnostic report should then show:

- `extra_update_packages: []`;
- `content_package_overlays.packages` listing the existing package(s) selected
  for Museum and banner files;
- `content_package_overlays.museum_catalog_ready: true` after the package
  response completes.

No original ZIP in the operator archive directory is modified.
