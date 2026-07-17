# v4.44 CN Museum bridge

- Keeps CN retained content version `97.4.6` unchanged.
- Adds opt-in extra update packages, defaulting to
  `data/cn_update_overlays/99_0_116.zip` when the file exists.
- Adds a generated plaintext Museum DB override for the NPPS4 server.
- Adds a deterministic CN/GL Museum analyzer and converter:
  - extracts both APKs' embedded Museum DBs;
  - decrypts Honky v4 CN and community files;
  - preserves the CN schema and all CN conflict rows;
  - imports only GL-only rows whose category is known to CN 9.7.1;
  - strips GL-only columns;
  - re-encrypts the result with the original CN file metadata;
  - wraps it in a real CN 99 package template as `99_0_116.zip`.
- Adds versioned Museum access policies:
  - `normal` keeps ordinary NPPS4 unlocks;
  - `archive` grants imported rows without a known achievement reward path;
  - `all` grants the full merged catalog.
- Adds `/npps4/android/museum-bridge.json` status output.
- Does not modify tutorial, Live, secretbox, friend, announcement, or CN version logic.
