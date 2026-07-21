# ZVY Persian Calendar

Jalali (Shamsi) calendar presentation layer for Odoo 19. Dates stay stored as
Gregorian ISO values in PostgreSQL; this module adds settings, session flags,
and a tested JavaScript conversion core for upcoming UI patches.

## Install (this Docker repo)

The module lives in `addons/zvy_persian_calendar` (mounted as
`/mnt/extra-addons`).

```bash
docker-compose restart odoo
```

Then in Odoo:

1. **Apps → Update Apps List**
2. Search **ZVY Persian Calendar** and install
3. **Settings → General Settings → Calendar** — enable **Jalali (Shamsi) Calendar**
4. Optional: **My Profile → Preferences → Jalali Calendar** — override per user

## Activation rules

| User preference | Result |
|-----------------|--------|
| **Default** | Active when company toggle is on **or** user language starts with `fa` |
| **Always use Jalali calendar** | Active regardless of company/language |
| **Never use Jalali calendar** | Inactive regardless of company/language |

When active, `session.jalali_calendar_enabled` is `true` in the browser session
(devtools → Application → session, or `/web/session/get_session_info`).

## Current scope (Phase 0 + 1)

- Installable module with company and user settings
- Session flag exposed to JavaScript (`jalali_service.isActive()`)
- Vendored [jalaali-js](https://github.com/jalaali/jalaali-js) conversion core
- JS unit tests (HOOT) and Python settings tests

UI patches (date fields, pickers, calendar view) are planned in later phases;
with the feature enabled today there is **no visible date formatting change yet**.

## Run tests

Python (inside the Odoo container):

```bash
odoo-bin -d <dbname> --test-tags /zvy_persian_calendar --stop-after-init
```

JavaScript unit tests run with the standard Odoo web unit test suite when
`web.assets_unit_tests` is loaded.

## License

Module: LGPL-3. Bundled `jalaali-js`: MIT (see `static/lib/jalaali/LICENSE`).
