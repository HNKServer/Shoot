# v4.35 CN home/announcement schema compatibility fix

This build continues from v4.34. It keeps the v4.34 fixes for idempotent starter unit selection and for moving NPPS4 docs away from `/main.php/api`.

Additional changes:

- Make `announce/checkState` match the honoka-style response shape and remove the extra `present_cnt` field.
- Replace the temporary announcement HTML with a honoka-like fixed-width WebView page.
- In CN compatibility mode, return safer honoka-style home/banner/payment/live SE/challenge values.
- Log CN `/main.php/api` batch module/action names to Android logcat so future native crashes can be correlated with the exact batch request.

No masterdata, resource archive, database migration, or WebUI translation logic was changed in this package.
