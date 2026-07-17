# v2.4 UI/path/service fixes

- Adds fixed centered top header: LoveArrowShoot! (#1769FF).
- Adds synchronized header hide/show toggle (▼ visible, ▲ hidden) on main and editor screens.
- Keeps scroll content able to occupy the top area when the fixed header is hidden.
- Reworks path mapping buttons into real actions: create/check public folders, check read/write, rewrite config.toml, Python self-check.
- Creates workspace static/templates folders to avoid FastAPI StaticFiles startup crash.
- Lets CN archive backend start even before the huge public CDN mirror is present.
