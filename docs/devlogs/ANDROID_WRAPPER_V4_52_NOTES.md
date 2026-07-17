# Android Wrapper v4.52

Strict baseline: v4.49.1.

- Retains CN content version 97.4.6.
- Leaves every operator-supplied 99 package untouched.
- Generates one independent 99_0_116 overlay containing only:
  - db/museum/museum.db_
  - assets/image/webview/npps4_data_transfer.png
  - assets/image/webview/npps4_manga.png
- Does not create 117 and does not edit 113/114/115.
- CN banner/bannerList returns two non-flipping type-2 cards for data transfer and manga.
- The transfer card uses a signed one-day user token and NPPS4's real handover state.
- CN Museum policy defaults to all and museum/info directly returns the complete merged catalog, matching honoka-chan's behavior without a 1360-row bind list.
- Removes the Go template wrappers accidentally left in manga.html.
- Preserves v4.49.1 Android editor/scrollbar and scouting fixes.
- A client which has already committed external_version 97.4.6 will not be forced to redownload any 99 package. Test the new overlay with a fresh/cleared CN game client data directory while preserving the Wrapper/server workspace backup.
