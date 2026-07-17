# Android Wrapper v4.30 notes

- Fix CN `/main.php/lbonus/execute` crash after selecting the initial member.
- Root cause: the editable login bonus provider may be loaded as an incomplete `types.SimpleNamespace` on Android, so `system/lbonus.py` crashed with `AttributeError: get_rewards`.
- Add a built-in safe login-bonus reward fallback used only when the configured provider lacks `get_rewards`.
- Does not change GL/JP normal custom login-bonus behavior when `external/login_bonus.py` is valid.
