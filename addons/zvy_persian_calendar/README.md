# ZVY Persian Calendar

Jalali (Shamsi) calendar presentation layer for Odoo 19. Dates stay stored as
Gregorian ISO values in PostgreSQL; this module adds settings, session flags,
a tested JavaScript conversion core, display formatting, a Jalali date picker,
Jalali headers/ranges in the Calendar app, and Jalali-aware search date filters.

## Install (this Docker repo)

The module lives in `addons/zvy_persian_calendar` (mounted as
`/mnt/extra-addons`).

```bash
docker-compose restart odoo
```

Then in Odoo:

1. **Apps → Update Apps List**
2. Search **ZVY Persian Calendar** and install (or **Upgrade** after code changes)
3. **Settings → General Settings → Calendar** — enable **Jalali (Shamsi) Calendar**
4. Optional: **My Profile → Preferences → Jalali Calendar** — override per user

Use **Developer Mode (with assets)** when iterating on JS patches.

Installing this module also installs the **Calendar** app (`calendar` dependency).

## Activation rules

| User preference | Result |
|-----------------|--------|
| **Default** | Active when company toggle is on **or** user language starts with `fa` |
| **Always use Jalali calendar** | Active regardless of company/language |
| **Never use Jalali calendar** | Inactive regardless of company/language |

When active, `session.jalali_calendar_enabled` is `true` in the browser session
(devtools → Application → session, or `/web/session/get_session_info`).

## Current scope

### Phase 0 + 1 (done)

- Installable module with company and user settings
- Session flag exposed to JavaScript (`jalali_service.isActive()`)
- Vendored [jalaali-js](https://github.com/jalaali/jalaali-js) conversion core
- JS unit tests (HOOT) and Python settings tests

### Phase 2A — Display formatting (done)

When Jalali is active, list and form fields **display** dates in Jalali via
`dates_patch.js` and `formatters_patch.js`. Server serialization is unchanged.

### Phase 2B — Date picker (done)

When Jalali is active:

- Popover calendar shows Jalali months, navigation, and year/decade pickers
- Day cells store Gregorian ISO internally; selection saves Gregorian to the ORM
- Manual input accepts Jalali strings (e.g. `1403/07/21`) on blur/Enter
- Placeholder shows a Jalali example format
- RTL styling on the picker (`jalali_calendar.scss`)

### Phase 3 — Calendar view (done)

When Jalali is active in the **Calendar** app:

- Month/week/day/year toolbar titles use Jalali (`Mehr 1403`, etc.)
- Month grid follows Jalali month boundaries (FullCalendar `visibleRange`)
- Column headers and day-cell numbers use Jalali day-of-month
- Prev/Next steps by Jalali month/week/day/year; **Today** jumps to local today
- Side-panel mini-calendar reuses the Phase 2B Jalali picker
- Year overview shows twelve Jalali months
- Event create/drag still stores Gregorian/UTC datetimes

### Phase 4 — Search filters (done)

When Jalali is active:

- Filters → Date period menu shows Jalali month names and years (e.g. `Mehr`, `1403`)
- “This month” / current month option uses Jalali month → Gregorian domain bounds
- “This year” / current year option is 1 Farvardin–29/30 Esfand → Gregorian range
- Quarters are Jalali seasons (Q1 Farvardin–Khordad … Q4 Dey–Esfand)
- Domain-selector custom range reuses the Phase 2B Jalali picker
- Domain-selector month/year presets (`Month to date`, `Year to date`, …) use Jalali bounds

**Note:** Filters “This year” means the **Jalali calendar year**, which often matches
Iranian fiscal year (1 Farvardin) but may differ from a company’s configured fiscal year.

### Manual test — picker + save

1. Enable **Jalali (Shamsi) Calendar** in Settings → General.
2. Open a contact → click **Birthday** → picker header shows a Jalali month (e.g. `Farvardin 1403`).
3. Pick a date or type `1403/07/21` → save.
4. DevTools → Network → `write` call: date value is Gregorian ISO (`2024-10-12`).
5. Disable Jalali + hard-refresh → stock Gregorian picker returns.

### Manual test — Calendar app

1. Upgrade module + hard-refresh (dev mode with assets).
2. Enable Jalali → open **Calendar** → **Month**: title is Jalali; cell numbers are Jalali.
3. Prev/Next crosses Esfand → Farvardin correctly.
4. Create or drag a meeting onto `1403/07/21` → Network payload start is Gregorian/UTC near `2024-10-12`.
5. Disable Jalali + hard-refresh → stock Gregorian calendar returns.

### Manual test — Search date filters

1. Upgrade module + hard-refresh (dev mode with assets).
2. Enable Jalali → open **Invoicing → Customers Invoices** (or any list with a Date filter).
3. Filters → **Invoice Date** (or **Date**): month labels are Jalali; years are Jalali (e.g. `1403`).
4. Select the **current month** (+ year if needed): facet shows Jalali month; Network `search_read` domain uses Gregorian ISO bounds for that Jalali month.
5. Clear → select the **current year** only: domain spans Farvardin 1–Esfand 29/30 of that Jalali year.
6. Add custom filter → date **is in** → **Custom range**: pickers show Jalali months; chosen bounds serialize as Gregorian.
7. Disable Jalali + hard-refresh → stock Gregorian period menu returns.

## Run tests

Python (inside the Odoo container):

```bash
odoo-bin -d <dbname> --test-tags /zvy_persian_calendar --stop-after-init
```

JavaScript unit tests run with the standard Odoo web unit test suite when
`web.assets_unit_tests` is loaded.

## License

Module: LGPL-3. Bundled `jalaali-js`: MIT (see `static/lib/jalaali/LICENSE`).
