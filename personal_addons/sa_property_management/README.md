# SA Property Management by SA Systems (Odoo 18 / 19)

End-to-end real estate **and construction** management module for any country,
with a country-aware tax engine.

## Features

### Real Estate

- **Project & Property Listing** — Housing societies, blocks, plots, apartments, commercial units.
- **Flexible Area Units** — Sq.Ft, Sq.Meter, Sq.Yard plus regional units (Marla, Kanal) pre-configured.
- **Payment Plans** — Down payment + N installments (monthly/quarterly/etc.) + balloon payments + on-possession charge, with optional **KIBOR / benchmark-linked variable rates**.
- **Bookings** — One-click booking confirmation auto-generates installment schedule and customer invoices.
- **Receivables Management** — Installment aging, overdue tracking, integrated with Odoo Accounting.
- **Investor Deals** — Secondary-market / investor resale tracking.
- **Dealership Management** — Dealers/agents with auto-computed commissions per booking.
- **Property Transfer System** — Owner-change workflow with a country-aware tax engine (transfer/stamp duty, registration, capital gains, VAT/GST, withholding) and configurable misc charges.
- **Buyback & Surrender** — Wizards for cancellations and repurchases.
- **Document Management** — Property paperwork plus QR-code verification.
- **Live Dashboard** — Bookings, receivables and payment-plan status.

### Construction

- **Construction Projects** — Broken down into phases with progress tracking.
- **Subcontracts** — Detailed Bill of Quantities (BOQ).
- **Interim Payment Certificates (IPC)** — Certify executed quantities and bill against the contract.
- **Material Requisitions** — Raise Purchase RFQs automatically.
- **Material Issues** — Issue to site with native Inventory stock moves.
- **Project Cost Model** — Built on Odoo Analytic Accounting and Timesheets.

### Platform

- **Fully Configurable Backend** — Operating country, every tax, charge, journal, account and default UoM is data-driven via Settings.
- **Reports** — Booking confirmation, payment schedule, transfer deed.

## Compatibility

- Odoo **18.0** and **19.0** (Community & Enterprise)
- License: **LGPL-3** (free / open source)
- Dependencies: `base`, `mail`, `account`, `product`, `sale_management`, `stock`, `purchase`, `project`, `hr_timesheet`, `portal`, `crm`

> The module uses modern Odoo view syntax (`<list>`, `<chatter/>`,
> `<app>/<block>/<setting>` settings, `@api.model_create_multi`), which
> requires **Odoo 18.0 as the minimum** supported series. It is verified to
> install and pass its test suite on both Odoo 18 and Odoo 19.

## Installation (Local Testing)

1. Copy the `sa_property_management` folder into your Odoo `addons` directory
   (or any path declared in `--addons-path`).
2. Start Odoo with the module path:
   ```bash
   ./odoo-bin -c odoo.conf -d test_db -i sa_property_management --without-demo=False
   ```
3. Or install from the UI: **Apps → Update Apps List → search "SA Property Management" → Install**.
4. For a clean local test database:
   ```bash
   ./odoo-bin -c odoo.conf -d sa_test --addons-path=/path/to/addons,./ \
       -i sa_property_management --log-level=info --stop-after-init
   ./odoo-bin -c odoo.conf -d sa_test
   ```

## Running Tests

```bash
./odoo-bin -c odoo.conf -d sa_test_run \
    -i sa_property_management --test-enable --stop-after-init --log-level=test
```

## Quick Tour

1. **Property Management → Configuration → Payment Plans** — create a plan
   (e.g. 20% down, 36 monthly installments, balloon at month 24, 10% on possession).
2. **Property Management → Configuration → Transfer Taxes & Misc Charges** —
   preset data seeds country-specific taxes and common charges for the selected market.
3. **Property Management → Projects** — create a project, then add properties.
4. **Property Management → Bookings** — create a booking, attach a payment plan, click **Confirm**.
   The schedule and the first invoice are generated automatically.
5. **Property Management → Receivables** — view all installments with aging.
6. **Property Management → Transfers** — initiate a property transfer, taxes &
   misc charges compute automatically, click **Approve** to finalise.

## Deployment

- Tested locally via the steps above.
- For Odoo.sh: push the module folder to your branch and rebuild.
- For on-premise: drop into `addons/`, restart Odoo, upgrade the module.

## Submission to apps.odoo.com

This module follows the official Odoo Apps guidelines:
- Valid manifest with all required keys (`name`, `version`, `license`, `category`, `summary`).
- LGPL-3 (free / open source) license file included.
- `static/description/index.html` description page (self-contained, inline-styled).
- No external Python deps; only uses Odoo core modules.
- Semantic version starts with the target Odoo major (`18.0.2.0.0` / `19.0.2.0.0`).
