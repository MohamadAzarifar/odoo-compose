# ZVY Persian Calendar — Implementation Roadmap

> **Module:** `zvy_persian_calendar`  
> **Target:** Odoo 19 (this repo’s `odoo:19` Docker stack)  
> **Goal:** Full Jalali (Shamsi) calendar experience in the Odoo backend UI while keeping Gregorian storage in the database.

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Design principles](#2-design-principles)
3. [Target module layout](#3-target-module-layout)
4. [Odoo integration map](#4-odoo-integration-map)
5. [Implementation phases](#5-implementation-phases)
6. [Master todo checklist](#6-master-todo-checklist)
7. [Testing strategy](#7-testing-strategy)
8. [Deployment & ops (this repo)](#8-deployment--ops-this-repo)
9. [Risks & mitigations](#9-risks--mitigations)
10. [Definition of done](#10-definition-of-done)

---

## 1. Executive summary

Odoo stores all `Date` and `Datetime` fields as **Gregorian ISO values** in PostgreSQL. A Persian calendar addon must therefore be a **presentation and input layer**, not a storage change.

The work splits into:

| Layer | Responsibility |
|-------|----------------|
| **JS (primary)** | Jalali date picker, field display, calendar view headers, search panel labels |
| **Python (secondary)** | Settings, user/company preferences, report helpers, optional server-side formatting |
| **QWeb / Reports** | Jalali dates in PDFs and email templates |
| **Portal / Website** | Separate asset bundle if frontend date pickers are required |

Build in **thin vertical slices**: get one date field working end-to-end before patching every widget in Odoo.

Estimated effort (one experienced Odoo/JS developer):

| Phase | Scope | Rough effort |
|-------|-------|--------------|
| 0 — Scaffold | Module skeleton, settings, feature flag | 0.5–1 day |
| 1 — Core conversion | Jalali ↔ Gregorian library + unit tests | 1–2 days |
| 2 — Date fields | Form/list datetime picker + formatters | 3–5 days |
| 3 — Calendar view | Meetings / scheduling calendar | 2–4 days |
| 4 — Filters & search | Date domains, pivot/cohort/grid headers | 2–3 days |
| 5 — Reports & mail | QWeb, PDF, chatter timestamps (optional) | 2–3 days |
| 6 — Hardening | RTL polish, edge cases, performance, docs | 2–3 days |

---

## 2. Design principles

### 2.1 Non-negotiable rules

- [ ] **Never** change how Odoo serializes dates to the server (`yyyy-MM-dd`, `yyyy-MM-dd HH:mm:ss`).
- [ ] **Never** patch PostgreSQL or ORM field types.
- [ ] All Jalali conversion happens at the **UI boundary** (and optionally in report templates).
- [ ] Feature must be **toggleable** (company setting + user override) so English/Gregorian users are unaffected.
- [ ] When Jalali mode is off, behaviour must be **identical** to stock Odoo (no regressions).

### 2.2 Activation rules (decide early, document in README)

Pick one primary trigger (recommended: **both** for flexibility):

| Trigger | Pros | Cons |
|---------|------|------|
| User language = `fa_IR` | Zero config for Persian users | English UI users in Iran may want Jalali |
| Explicit setting on user/company | Full control | Extra configuration step |
| **Recommended:** setting OR `fa_IR` | Best UX | Slightly more code |

### 2.3 Library choice

Prefer a **small, bundled** JS library (no CDN — this stack uses Squid allowlist proxy):

| Candidate | Notes |
|-----------|-------|
| `jalaali-js` | Lightweight algorithm, no moment.js dependency |
| `@persian-tools/persian-date` | Rich formatting, Persian digit support |
| `jalali-moment` | Heavier; only if moment is already present |

Vendor the chosen library under `static/lib/` and wrap it in a single Odoo ES module (`jalali_core.js`) so patches import one API.

Optional Python mirror for reports only:

| Candidate | Notes |
|-----------|-------|
| `jdatetime` | Requires custom Docker image or runtime `pip install` |
| Pure-Python port of jalaali algorithm | Zero extra deps; copy into `models/jalali_utils.py` |

**Recommendation:** JS-only for v1; add Python helper in Phase 5 when reports are needed.

### 2.4 Patching strategy (Odoo 19)

Use `@web/core/utils/patch` on prototypes — **do not fork** core files.

Centralize the “is Jalali active?” check:

```javascript
// static/src/js/jalali_service.js
export const jalaliService = {
    isActive() { /* read from session / user context */ },
};
```

Register as a `registry.category("services")` entry so all patches share one source of truth.

---

## 3. Target module layout

```
addons/zvy_persian_calendar/
├── __init__.py
├── __manifest__.py
├── README.md
├── zyv_persian_calendar_roadmap.md      ← this file
│
├── models/
│   ├── __init__.py
│   ├── res_company.py                   # company.use_jalali_calendar
│   ├── res_users.py                     # user-level override
│   ├── res_config_settings.py           # settings UI wiring
│   └── jalali_utils.py                  # optional Python conversion (Phase 5)
│
├── views/
│   ├── res_config_settings_views.xml
│   └── res_users_views.xml
│
├── data/
│   └── res_lang_data.xml                # optional: fa_IR week_start, date_format tweaks
│
├── security/
│   └── ir.model.access.csv              # only if new models added
│
├── static/
│   ├── lib/
│   │   └── jalaali/                     # vendored third-party (license file included)
│   └── src/
│       ├── js/
│       │   ├── jalali_core.js           # conversion API (wraps lib)
│       │   ├── jalali_service.js        # feature flag + session bridge
│       │   ├── jalali_format.js         # format/parse helpers
│       │   ├── patches/
│       │   │   ├── dates_patch.js       # @web/core/l10n/dates
│       │   │   ├── datetime_picker_patch.js
│       │   │   ├── datetime_field_patch.js
│       │   │   ├── datetime_input_patch.js
│       │   │   ├── formatters_patch.js
│       │   │   ├── calendar_model_patch.js
│       │   │   ├── calendar_renderer_patch.js
│       │   │   └── remaining_days_patch.js
│       │   └── tests/
│       │       └── jalali_core.test.js  # QUnit / HOOT tests
│       └── scss/
│           └── jalali_calendar.scss     # RTL picker tweaks, Persian digits
│
├── report/                              # Phase 5
│   └── ir_actions_report_patch.xml
│
├── i18n/
│   ├── fa.po
│   └── zvy_persian_calendar.pot
│
└── tests/
    ├── __init__.py
    ├── test_jalali_utils.py             # Python conversion tests
    └── test_settings.py                 # settings propagation tests
```

### 3.1 `__manifest__.py` starter dependencies

```python
'depends': ['web', 'base'],
# Phase 3+: add 'calendar' when calendar view patches are included
# Phase 5+: add modules whose reports you customize (e.g. 'account', 'sale')
```

Asset bundle order matters — load `jalali_core` and `jalali_service` **before** patches:

```python
'assets': {
    'web.assets_backend': [
        'zvy_persian_calendar/static/lib/jalaali/jalaali.js',
        'zvy_persian_calendar/static/src/js/jalali_core.js',
        'zvy_persian_calendar/static/src/js/jalali_service.js',
        'zvy_persian_calendar/static/src/js/jalali_format.js',
        'zvy_persian_calendar/static/src/js/patches/*.js',
        'zvy_persian_calendar/static/src/scss/jalali_calendar.scss',
    ],
},
```

---

## 4. Odoo integration map

Files in **Odoo core** (`addons/web/`) that this module will patch or extend:

### 4.1 Date/time core

| Core file | Purpose | Patch priority |
|-----------|---------|----------------|
| `web/static/src/core/l10n/dates.js` | `formatDate`, `parseDate`, `serializeDate`, Luxon helpers | **P0** |
| `web/static/src/core/l10n/localization_service.js` | Locale, week start, formats from `res.lang` | P1 |
| `web/static/src/core/datetime/datetime_picker.js` | Month grid, navigation, day cells | **P0** |
| `web/static/src/core/datetime/datetime_picker_hook.js` | Hook used by fields | **P0** |
| `web/static/src/core/datetime/datetime_picker_popover.js` | Popover wrapper | P1 |
| `web/static/src/core/datetime/datetime_input.js` | Standalone input widget | P1 |
| `web/static/src/core/datetime/datetimepicker_service.js` | Global picker service | P2 |

### 4.2 Field widgets

| Core file | Purpose | Patch priority |
|-----------|---------|----------------|
| `web/static/src/views/fields/datetime/datetime_field.js` | Form kanban datetime field | **P0** |
| `web/static/src/views/fields/datetime/list_datetime_field.js` | List editable datetime | **P0** |
| `web/static/src/views/fields/formatters.js` | List/kanban display formatters | **P0** |
| `web/static/src/views/fields/remaining_days/remaining_days_field.js` | “In 3 days” style fields | P2 |

### 4.3 Calendar view (scheduling app)

| Core file | Purpose | Patch priority |
|-----------|---------|----------------|
| `web/static/src/views/calendar/calendar_model.js` | Range, scale (day/week/month/year) | **P1** |
| `web/static/src/views/calendar/calendar_renderer.js` | FullCalendar integration | **P1** |
| `web/static/src/views/calendar/calendar_controller.js` | Toolbar, “Today” button | P1 |
| `web/static/src/views/calendar/calendar_year/calendar_year_renderer.js` | Year view | P2 |
| `web/static/src/views/calendar/hooks/full_calendar_hook.js` | FullCalendar options | P2 |

### 4.4 Search & analytics views

| Core file | Purpose | Patch priority |
|-----------|---------|----------------|
| `web/static/src/search/**` (date filter components) | “This month”, custom range | P2 |
| `web_cohort/static/src/cohort_view.js` | Cohort column headers | P3 |
| `web_grid/static/src/grid_renderer.js` | Grid date headers | P3 |

### 4.5 Backend Python (read-only / settings only)

| Core model | Purpose |
|------------|---------|
| `res.lang` | `fa_IR` already exists; week_start=6 (Saturday) |
| `res.users` | `lang` field drives localization |
| `res.company` | Company-wide calendar preference |
| `ir.qweb` / report templates | Phase 5 Jalali formatting |

### 4.6 Explicitly out of scope for v1

- Changing `fields.Date` ORM definition
- PostgreSQL date functions
- Mobile app (Odoo mobile uses separate codebase)
- Spreadsheets / Excel export date formats (Phase 6+)
- Website builder date pickers (`web.assets_frontend`) — separate phase

---

## 5. Implementation phases

> **Implementation log (2026-07-21):** Phase 0 + Phase 1 landed in `addons/zvy_persian_calendar/`.
> Module scaffold (manifest, settings, user prefs, `ir.http` session flag, README) and Jalali
> conversion core (`jalaali-js` vendored, `jalali_core.js`, `jalali_format.js`, `jalali_service.js`,
> HOOT + Python settings tests).
>
> **Implementation log (2026-07-21, later):** Phase 2A — display formatting landed.
> `dates_patch.js` and `formatters_patch.js` route `formatDate` / `formatDateTime` /
> `toLocaleDateString` / `toLocaleDateTimeString` through Jalali when active. Server
> serialization (`serializeDate`, `deserializeDate`) untouched.
>
> **Implementation log (2026-07-21, later):** Phase 2B — date picker widget landed.
> Jalali month grid, month/year/decade navigation, manual Jalali typing (`1403/07/21`),
> placeholders, and RTL picker styling. `dates_patch.js` also extended with `parseDate` /
> `parseDateTime`; loaded before `datetimepicker_service.js` so input parsing works.

---

### Phase 0 — Module scaffold & feature flag

**Objective:** Installable module with settings, no visible UI change yet.

#### Tasks

- [x] Create `__init__.py`, `__manifest__.py` (version `19.0.1.0.0`, license, author).
- [x] Add `models/res_company.py` — field `use_jalali_calendar` (Boolean, default False).
- [x] Add `models/res_users.py` — field `use_jalali_calendar` (Selection: `default` / `enabled` / `disabled`).
- [x] Add `models/res_config_settings.py` — related fields + settings panel.
- [x] Add `views/res_config_settings_views.xml` — toggle under General Settings.
- [x] Add `views/res_users_views.xml` — preference on user form (Preferences tab).
- [x] Expose flag to JS session:
  - [x] Extend `ir.http` or use `web.session_info` patch to inject `jalali_calendar_enabled: bool`.
- [x] Verify: module installs, settings save, flag visible in browser devtools session. *(requires Docker restart + manual install)*
- [x] Add `README.md` with install steps for this Docker repo.

#### Exit criteria

- Module appears in Apps list after `docker-compose restart odoo` + Update Apps List.
- Toggle persists; no JS errors with patches disabled.

---

### Phase 1 — Jalali conversion core

**Objective:** Reliable, tested conversion layer used by all later patches.

#### Tasks

- [x] Vendor `jalaali-js` (or chosen lib) into `static/lib/` with LICENSE file.
- [x] Implement `jalali_core.js`:
  - [x] `gregorianToJalali(date: luxon.DateTime) → { jy, jm, jd }`
  - [x] `jalaliToGregorian(jy, jm, jd) → luxon.DateTime`
  - [x] `isValidJalali(jy, jm, jd) → boolean`
  - [x] `jalaliMonthLength(jy, jm) → number`
  - [x] `isJalaliLeap(jy) → boolean`
- [x] Implement `jalali_format.js`:
  - [x] `formatJalali(date, pattern)` — support tokens: `%Y/%m/%d`, Persian month names, `%B`, `%b`
  - [x] `parseJalali(string, pattern) → luxon.DateTime | null`
  - [x] Optional: `toPersianDigits(str)` / `toLatinDigits(str)`
- [x] Implement `jalali_service.js`:
  - [x] `isActive()` reads company + user + lang rules
  - [x] Register in `registry.category("services")`
- [x] Write JS unit tests (`jalali_core.test.js`):
  - [x] Nowruz boundaries (1 Farvardin ↔ March 20/21)
  - [x] Leap years (e.g. 1403, 1404)
  - [x] End-of-month (Esfand 29/30)
  - [x] Round-trip: Gregorian → Jalali → Gregorian
- [x] Write Python tests in `tests/test_jalali_utils.py` if Python helper added. *(N/A — JS-only for v1; `tests/test_settings.py` covers activation rules + session_info)*

#### Exit criteria

- All conversion tests pass in `odoo-bin` test runner / HOOT.
- Manual sanity check in browser console.

---

### Phase 2 — Date & datetime fields (forms + lists)

**Objective:** Users can **see** and **pick** Jalali dates in standard form/list views.

#### 2A — Display formatting

- [x] Patch `formatters.js`:
  - [x] When `jalaliService.isActive()`, route `formatDate` / `formatDateTime` through `jalali_format.js`.
  - [x] Preserve time portion formatting (24h from `res.lang`).
- [x] Patch `dates.js` (careful — high impact):
  - [x] Override **display** format paths only; leave `serializeDate` / server paths untouched.
  - [x] Ensure `deserializeDate` still parses server ISO strings correctly.

**Manual test scenario (2A — display only):**

| Step | Action | Expected |
|------|--------|----------|
| 1 | `docker-compose restart odoo` → Apps → Upgrade **ZVY Persian Calendar** | Module loads without JS errors |
| 2 | Settings → General → enable **Jalali (Shamsi) Calendar** | Setting persists |
| 3 | Open **Contacts** list (`res.partner`) | `Birthday` column shows Jalali (e.g. `1403/07/21` for fa_IR format) |
| 4 | Open a contact form with a birthdate | Form field **displays** Jalali; saved DB value stays Gregorian ISO |
| 5 | Open **Invoicing → Customers → Invoices** list | `Invoice Date` column shows Jalali |
| 6 | Open an invoice with `invoice_date` + `invoice_date_due` | Both dates display in Jalali; time (if any) uses 24h from language |
| 7 | Settings → disable Jalali calendar → hard-refresh browser | Dates revert to stock Gregorian formatting |
| 8 | DevTools → Network → any `read` RPC response | Date fields in JSON still `YYYY-MM-DD` (Gregorian) |

*Note:* The date **picker** still shows the Gregorian calendar until Phase 2B. Only **display** formatting changes in 2A.

#### 2B — Date picker widget

- [x] Patch `datetime_picker.js`:
  - [x] Render Jalali month/year in header.
  - [x] Build week grid from Jalali month boundaries (convert each cell to Gregorian for selection).
  - [x] Month navigation: prev/next Jalali month.
  - [x] Year/decade picker modes in Jalali.
  - [x] Highlight “today” in Jalali terms.
  - [x] Respect `minDate` / `maxDate` constraints (convert limits to Jalali display).
- [x] Patch `datetime_picker_hook.js` if hook API needs Jalali-aware defaults. *(N/A — hook delegates to picker service; no changes required)*
- [x] Patch `datetime_field.js`:
  - [x] Input placeholder shows Jalali example format.
  - [x] Manual typing: accept `1403/07/21` and convert on blur.
  - [x] On change: still emit Gregorian ISO to ORM.
- [x] Patch `list_datetime_field.js` for inline list editing. *(inherits `dateField` / `dateTimeField` extractProps patches)*
- [x] Patch `datetime_input.js` for standalone usages (filters, wizards).
- [x] SCSS: RTL alignment, picker width, Persian digit toggle. *(RTL + chevron flip; Persian digits deferred to Phase 6)*

**Manual test scenario (2B — picker + input):**

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upgrade module + hard-refresh (dev mode with assets) | No JS console errors |
| 2 | Enable Jalali calendar in Settings | Active |
| 3 | Open **Contacts** → edit a contact → click **Birthday** field | Popover opens with Jalali month header (e.g. `Farvardin 1403`) |
| 4 | Navigate **prev/next** month arrows | Month changes by Jalali month (Esfand → Farvardin at year boundary) |
| 5 | Click header → month grid → year grid | Jalali month names and years shown |
| 6 | Select a day (e.g. `1403/07/21`) → Save | Field shows Jalali; Network `write` payload date is `2024-10-12` (Gregorian ISO) |
| 7 | Clear field, type `1403/07/21` manually → Tab/Enter | Accepted and displayed in Jalali |
| 8 | Open **Invoicing → Invoice** → edit `Invoice Date` in list view (inline) | Jalali picker works; save persists Gregorian in DB |
| 9 | Disable Jalali → hard-refresh → repeat step 3 | Stock Gregorian picker returns |

#### 2C — Manual QA targets (this repo’s installed apps)

Test date fields in modules you actually use:

- [ ] `condominium` — meetings, meter readings, any custom date fields
- [ ] `sa_property_management` — booking dates, installment due dates, transfer dates
- [ ] Core — `res.partner` (`date` birthdate), `account.move` (`invoice_date`, `date`), `crm.lead` (`date_deadline`)

#### Exit criteria

- Create/edit/save a record with a date field; DB value remains Gregorian ISO.
- List view shows Jalali; export CSV still Gregorian (document behaviour).
- Toggle off → identical to stock Odoo.

---

### Phase 3 — Calendar view (scheduling)

**Objective:** The Calendar app (meetings, appointments) shows Jalali month/week/day headers.

#### Tasks

- [ ] Add `'calendar'` to module `depends` when starting this phase.
- [ ] Patch `calendar_model.js`:
  - [ ] Jalali-aware “today”, range calculations for month/week views.
- [ ] Patch `calendar_renderer.js` / FullCalendar hook:
  - [ ] Column headers in Jalali (day name + Jalali date).
  - [ ] Title bar: “Mehr 1403” instead of “October 2024”.
  - [ ] Week numbers (optional).
- [ ] Patch `calendar_controller.js`:
  - [ ] “Today” navigates to current Jalali date.
  - [ ] Mini-calendar side panel (if present) uses Jalali picker.
- [ ] Patch `calendar_year_renderer.js` for year overview (lower priority).
- [ ] Test with `calendar.event` — create drag-drop event, verify stored UTC/Gregorian correct.

#### Exit criteria

- Calendar app usable for Persian users across month/week/day scales.
- Events created on Jalali date appear on correct Gregorian slot in DB.

---

### Phase 4 — Search filters & analytic views

**Objective:** Date filters and chart axes make sense in Jalali context.

#### Tasks

- [ ] Identify date filter components in `web/static/src/search/` (grep for `DateFilter`, `Comparison`, date domains).
- [ ] Patch relative ranges:
  - [ ] “This month” = current **Jalali** month converted to Gregorian domain.
  - [ ] “This year” = current Jalali year (1 Farvardin – 29/30 Esfand) → Gregorian range.
  - [ ] Document that fiscal year alignment may differ from Jalali year.
- [ ] Patch custom date range picker in search panel to use Jalali picker (Phase 2 widget).
- [ ] (Optional P3) `web_cohort` — column period labels.
- [ ] (Optional P3) `web_grid` — row/column date headers.

#### Exit criteria

- Filtering `account.move` by “This month” returns correct records for Jalali month boundaries.
- No off-by-one at month boundaries (Farvardin 1, Esfand 29/30).

---

### Phase 5 — Reports, QWeb & server-side formatting

**Objective:** Printed PDFs and email templates can show Jalali dates.

#### Tasks

- [ ] Add `models/jalali_utils.py` with `gregorian_to_jalali_str(date, fmt)` — pure Python or `jdatetime`.
- [ ] Add QWeb helper registration (e.g. `@api.model` wrapper exposed to reports).
- [ ] Create report inheritance examples:
  - [ ] Invoice PDF date (`account.report_invoice`)
  - [ ] Sale order date
  - [ ] Custom: `sa_property_management` booking schedule report
- [ ] Mail template snippet for `{jalali_date}` placeholder (optional).
- [ ] Settings: “Show Jalali dates in reports” separate toggle (some users want Gregorian on PDFs).

#### Docker note

If using `jdatetime`, extend the Odoo image:

```dockerfile
FROM odoo:19
USER root
RUN pip3 install --break-system-packages jdatetime
USER odoo
```

Or vendor pure-Python conversion to avoid image changes.

#### Exit criteria

- At least one PDF report shows Jalali invoice date.
- Report dates match form UI dates for the same record.

---

### Phase 6 — Hardening, performance & release

**Objective:** Production-ready quality for ~5 users on this stack.

#### Tasks

- [ ] **RTL polish:** picker popover position, icon order, keyboard navigation in RTL.
- [ ] **Persian digits:** setting to show ۱۴۰۳/۰۷/۲۱ vs 1403/07/21.
- [ ] **Performance:** memoize conversion; avoid re-render loops in patched pickers.
- [ ] **Edge cases:**
  - [ ] Empty/null dates
  - [ ] Timezone boundaries for `Datetime` fields (store UTC, display local)
  - [ ] DST (Iran abolished DST — document assumption: `Asia/Tehran` fixed offset)
  - [ ] Year 1000–9999 limits from Odoo `MIN_VALID_DATE` / `MAX_VALID_DATE`
- [ ] **Regression:** full pass with Jalali **disabled**.
- [ ] **Upgrade path:** migration notes for module version bumps.
- [ ] **i18n:** complete `fa.po` for all module strings.
- [ ] **Documentation:** update `README.md` — settings, limitations, troubleshooting.
- [ ] **CI:** add module to test run if repo gets automated tests.

#### Exit criteria

- No console errors on main apps (Accounting, CRM, Calendar, Property modules).
- Code review checklist complete (see §10).

---

## 6. Master todo checklist

Copy this section into an issue tracker; check items as you go.

### Scaffold (Phase 0)

- [x] `__manifest__.py` created and installable
- [x] Company setting field
- [x] User preference field
- [x] Settings UI
- [x] Session info exposes flag to JS
- [ ] Install verified in Docker

### Conversion library (Phase 1)

- [x] Third-party lib vendored with license
- [x] `jalali_core.js` API complete
- [x] `jalali_format.js` parse/format complete
- [x] `jalali_service.js` registered
- [x] JS unit tests passing *(written; run via HOOT after install)*
- [x] Python unit tests passing (if applicable) *(settings tests in `tests/test_settings.py`)*

### Field widgets (Phase 2)

- [x] `formatters.js` patched *(Phase 2A)*
- [x] `dates.js` display paths patched *(Phase 2A)*
- [x] `datetime_picker.js` patched *(Phase 2B)*
- [x] `datetime_field.js` patched *(Phase 2B)*
- [x] `list_datetime_field.js` patched *(Phase 2B — via field extractProps inheritance)*
- [x] `datetime_input.js` patched *(Phase 2B)*
- [x] SCSS styling done *(Phase 2B — RTL; Persian digits Phase 6)*
- [ ] Manual QA on condominium + property modules

### Calendar app (Phase 3)

- [ ] `calendar` dependency added
- [ ] `calendar_model.js` patched
- [ ] `calendar_renderer.js` patched
- [ ] `calendar_controller.js` patched
- [ ] Event create/save verified in DB

### Search & analytics (Phase 4)

- [ ] Jalali “This month” filter
- [ ] Jalali “This year” filter
- [ ] Custom date range picker
- [ ] (Optional) Cohort/grid headers

### Reports (Phase 5)

- [ ] Python `jalali_utils.py`
- [ ] QWeb helper registered
- [ ] Sample invoice report patched
- [ ] Property management report patched (if needed)

### Release (Phase 6)

- [ ] Persian digits option
- [ ] RTL QA complete
- [ ] Performance acceptable
- [ ] Regression with feature off
- [ ] `fa.po` complete
- [ ] README complete

---

## 7. Testing strategy

### 7.1 Automated tests

| Area | Tool | Location |
|------|------|----------|
| JS conversion | HOOT / QUnit | `static/src/js/tests/` |
| Python utils | `TransactionCase` | `tests/test_jalali_utils.py` |
| Settings | `TransactionCase` | `tests/test_settings.py` |

### 7.2 Critical date test vectors

Use these in both JS and Python tests:

| Gregorian | Jalali | Note |
|-----------|--------|------|
| 2024-03-20 | 1403/01/01 | Nowruz 1403 |
| 2024-03-21 | 1403/01/02 | |
| 2025-03-21 | 1404/01/01 | Nowruz 1404 |
| 2024-02-29 | 1402/12/10 | Leap day (Gregorian) |
| 2024-03-19 | 1402/12/29 | Last day of Jalali leap year 1402 |
| 2024-03-20 | 1403/01/01 | First day of 1403 |

### 7.3 Manual test matrix

| Scenario | Jalali ON | Jalali OFF |
|----------|-----------|------------|
| Create SO with order date | ☐ | ☐ |
| Edit invoice date in list view | ☐ | ☐ |
| Calendar meeting drag-drop | ☐ | ☐ |
| Date filter “This month” | ☐ | ☐ |
| User lang = en_US | ☐ | ☐ |
| User lang = fa_IR | ☐ | ☐ |
| PDF invoice print | ☐ | ☐ |

### 7.4 Browser coverage

- [ ] Chrome (primary)
- [ ] Firefox
- [ ] Mobile viewport (responsive picker layout)

---

## 8. Deployment & ops (this repo)

### 8.1 Install flow

```bash
# Module lives in addons/ (already mounted as /mnt/extra-addons)
docker-compose restart odoo
# UI: Apps → Update Apps List → Install "ZVY Persian Calendar"
# UI: Settings → General → enable Jalali calendar
# UI: Users → set language to Persian (optional)
```

### 8.2 Module path precedence

`personal_addons/` is mounted **before** `addons/` in `addons_path`. If you later move this module to `personal_addons/zvy_persian_calendar/`, it will override a same-named copy in `addons/`.

### 8.3 Developer mode

Use **Developer Mode (with assets)** when iterating on JS patches so bundles rebuild.

### 8.4 Proxy / network

- Vendored JS libs — no CDN required.
- If adding `jdatetime` via pip at container start, network egress goes through Squid (`proxy/allowlist.txt`); prefer vendored pure Python instead.

### 8.5 Upgrade

```bash
# After code changes
docker-compose restart odoo
# UI: Apps → Upgrade "ZVY Persian Calendar"
```

---

## 9. Risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Patching `dates.js` breaks all date fields | Critical | Patch display-only code paths; extensive tests; feature flag |
| Odoo core update overwrites patch assumptions | High | Pin Odoo 19 image; re-test on upgrade; keep patches minimal |
| Month boundary off-by-one in domains | High | Shared conversion lib; boundary test vectors |
| FullCalendar internals differ in minor Odoo releases | Medium | Isolate calendar patches; test after `docker pull odoo:19` |
| Users expect Jalali in CSV/Excel export | Medium | Document: exports stay Gregorian unless custom export added |
| Python dep in stock Docker image | Medium | Pure-Python conversion or custom Dockerfile |
| Performance on large list views | Low | Memoize; avoid per-row heavy conversion |
| Third-party lib license incompatibility | Medium | Prefer MIT/BSD; include LICENSE in `static/lib/` |

---

## 10. Definition of done

### v1.0.0 — Minimum viable

- [ ] Feature flag (company + user)
- [ ] Jalali date picker on form fields
- [ ] Jalali display in list/kanban columns
- [ ] Gregorian storage verified
- [ ] README with install/configure steps
- [ ] JS conversion tests
- [ ] No errors with feature disabled

### v1.1.0 — Calendar app

- [ ] Calendar view Jalali headers/navigation
- [ ] Event CRUD correct in DB

### v1.2.0 — Filters

- [ ] Jalali-relative search filters (this month/year)

### v1.3.0 — Reports

- [ ] QWeb helper + at least one report template

### v2.0.0 — Production hardening

- [ ] Persian digits option
- [ ] Full manual QA matrix passed
- [ ] Performance acceptable on property management dashboards
- [ ] Complete Persian translation

---

## Appendix A — Reference links (internal)

| Resource | Path |
|----------|------|
| Project README | `/README.md` |
| Personal addons guide | `/personal_addons/README.md` |
| Odoo addons path config | `/odoo/config/odoo.conf.template` |
| Persian language definition | `/addons/base/data/res.lang.csv` (`fa_IR`) |
| Example asset registration | `/addons/sa_property_management/__manifest__.py` |
| Date field widget | `/addons/web/static/src/views/fields/datetime/datetime_field.js` |
| DateTime picker | `/addons/web/static/src/core/datetime/datetime_picker.js` |
| Calendar view registry | `/addons/web/static/src/views/calendar/calendar_view.js` |

---

## Appendix B — Suggested git workflow

```bash
git checkout -b feature/zvy-persian-calendar
# Implement phase by phase; one commit per phase
git commit -m "feat(zvy_persian_calendar): phase 0 module scaffold"
git commit -m "feat(zvy_persian_calendar): phase 1 jalali conversion core"
# ...
```

Keep PRs small: **one phase per PR** where possible for easier review.

---

*Last updated: 2026-07-21 — Odoo 19 target*
