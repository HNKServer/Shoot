# Android Wrapper v4.13

Fixes the CN SIF1 `/main.php/login/authkey` loop introduced after v4.12 changed the failure from HTTP 422 to HTTP 400 `Bad client key`.

The uploaded CN client is honoka-chan/Termux-oriented and encrypts the SIF game-layer `dummy_token` with honoka-chan's RSA public key. Older wrapper builds copied NPPS4's upstream sample `default_server_key.pem` into the Android workspace, so RSA decrypt returned an empty client key and `/login/authkey` returned `400 Bad Request`.

Changes:

- Replace bundled `app/src/main/python/default_server_key.pem` with honoka-chan's `assets/certs/privatekey.pem` from the uploaded original honoka-chan source tree.
- During `prepare_workspace`, overwrite only the known stale NPPS4 sample key in the mutable Android workspace and back it up as `default_server_key.pem.npps4-sample.bak`.
- Do not overwrite unknown/custom keys.

After installing this build, force-stop the wrapper once, start the server again, then retest the CN client. The next checkpoint is whether `/main.php/login/authkey` changes from `400 Bad client key` to `200 OK`.
