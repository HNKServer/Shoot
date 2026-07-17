# Android Wrapper v4.23 - CN honoka-style server_info override fix

This version intentionally reverts the experimental v4.22 one-pass CN download change and is based on the v4.21 behavior.

## Why v4.22 was reverted

The CN client/honoka-chan standard flow is two-stage:

1. First boot downloads a small 99_0_* update set.
2. After restart, the client displays the basic/full data download dialog and enters the large data download flow.

v4.22 incorrectly tried to merge the later package_list resources into /download/update. That made the initial update stage less compatible with the CN client and could make the client fall back to the original SDO endpoint.

## Fix in v4.23

v4.19-v4.21 served a tiny replacement 99_0_115.zip containing only config/server_info.json. honoka-chan's deployment notes instead build 99_0_115.zip by copying a real 99 update package such as 99_0_113.zip, removing client_info.json, and replacing config/server_info.json.

v4.23 now follows that shape:

- Keep v4.21 update flow: /download/update only returns 99 update packages when external_version != 97.4.6.
- Do not merge package_list resources into /download/update.
- Generate a honoka-style 99_0_115.zip from a real 99_0_* template when available.
- Serve the generated ZIP under the public name 99_0_115.zip.
- Fall back to the bundled tiny override only if no real template exists, with a preflight warning.
- Enable honoka-style CN main response headers for CN profiles.
- Migrate existing Android cn_archive configs from cn_main_headers=false to true.
- Add compact CN download/update and download/batch diagnostic logs.

## Expected CN test flow

Clear the broken client state left by v4.22 or older tests:

```bash
adb shell pm clear klb.android.lovelivecx
```

Start v4.23, select the CN local cn_archive profile, restart the server, then start the CN client.

Expected behavior:

1. First boot downloads a small 99_0_* update set.
2. Client restarts.
3. The next boot shows the basic/full data download dialog and starts the large resource flow.

If step 3 still fails, collect logcat and the NPPS4 wrapper log around `CN download/update`, `CN download/batch`, `/download/additional`, and `/download/getUrl`.
