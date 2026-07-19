# -*- coding: utf-8 -*-
{
    'name': "SA Property Management",
    'summary': "End-to-end real estate AND construction management for any "
               "country: listings, payment plans, receivables, dealerships, "
               "investor deals, property transfers and a full construction "
               "suite (projects, subcontracts/BOQ, IPCs, procurement) with a "
               "country-aware tax engine.",
    'description': """
SA Property Management
======================

A complete, **country-agnostic** real-estate **and construction** management
solution. Works out of the box for any market — pick your operating country in
the settings and the matching transfer taxes and charges are applied
automatically. Runs on **Odoo 18.0 and 19.0** from a single codebase.

Real-Estate Features
--------------------
* **Property Listing** with flexible Units of Measure (Sq.Ft, Sq.Meter,
  Sq.Yard, plus regional units such as Marla and Kanal).
* **Project / Housing Society** management with blocks, streets and plot numbers.
* **Payment Plan Builder** (Down Payment + Monthly/Quarterly/Half-Yearly/Yearly
  installments + Balloon Payments + On-Possession charge), with optional
  **KIBOR / benchmark-linked variable rates**.
* **Booking Workflow** that auto-generates the installment schedule and
  customer invoices through standard Odoo Accounting.
* **Receivables Management** with installment aging, overdue tracking and
  registered payment integration.
* **Investor Deals** for secondary-market / investor resale tracking.
* **Dealership Management** with per-booking **commission** calculation.
* **Property Transfers** with a country-aware tax breakdown and transfer deed.
* **Buyback & Surrender** wizards for cancellations and repurchases.
* **Document Management** for property paperwork, plus QR-code verification.
* **Live Dashboard** for bookings, receivables and payment-plan status.

Construction Management
-----------------------
A full contractor / developer construction suite:

* **Construction Projects** broken down into **Phases** with progress tracking.
* **Subcontracts** with a detailed **Bill of Quantities (BOQ)**.
* **Interim Payment Certificates (IPC)** that certify executed quantities and
  bill against the contract.
* **Material Requisitions** that raise **Purchase RFQs** automatically.
* **Material Issues** to site with native **Inventory** stock moves.
* **Project Cost Model** built on Odoo **Analytic Accounting** and Timesheets.

Country-Aware Tax Engine
------------------------
Define transfer taxes (transfer/stamp duty, registration, capital gains,
VAT/GST, withholding, etc.) and miscellaneous charges per country, then select
the relevant country in Configuration. Ready-made presets ship for several
markets and you can add your own — no hard-coded country logic.

Built On
--------
Leverages Odoo core: ``account``, ``product``, ``sale_management``, ``stock``,
``purchase``, ``project``, ``hr_timesheet``, ``mail``, ``portal`` and ``crm``.
No external Python dependencies — deploys on Odoo.sh and on-premise (Community
or Enterprise).

Compatibility
-------------
Verified on **Odoo 18.0 and 19.0** (Community) — 49 automated tests pass on
both series.
    """,
    'author': "SA Systems",
    'maintainer': "SA Systems",
    'website': "https://sasystems.solutions/custom-web-app-development",
    'support': "info@sasystems.solutions",
    'license': 'LGPL-3',
    'category': 'Services/Real Estate',
    # Series-agnostic version so the module installs on Odoo 18 and 19 alike
    # (a "19.0.x" string is rejected by Odoo 18, and vice-versa). Odoo prefixes
    # the running series automatically, so this reports as 2.0 on both.
    'version': '19.0.2.0.0',
    'application': True,
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',

    'depends': [
        'base',
        'mail',
        'account',
        'product',
        'portal',
        'crm',
        'sale_management',
        'stock',
        'purchase',
        'project',
        'hr_timesheet',
    ],

    'data': [
        # security
        'security/sa_property_security.xml',
        'security/ir.model.access.csv',
        # data
        'data/ir_sequence_data.xml',
        'data/product_category_data.xml',
        'data/property_area_uom_data.xml',
        'data/transfer_tax_data.xml',
        'data/misc_charge_data.xml',
        'data/service_data.xml',
        'data/kibor_rate_data.xml',
        # wizards
        'wizards/sa_booking_confirm_wizard_views.xml',
        'wizards/sa_installment_payment_wizard_views.xml',
        'wizards/sa_property_transfer_wizard_views.xml',
        'wizards/sa_property_buyback_wizard_views.xml',
        'wizards/sa_property_surrender_wizard_views.xml',
        'wizards/sa_lead_import_wizard_views.xml',
        # reports
        'reports/report_paperformat.xml',
        'reports/sa_booking_report.xml',
        'reports/sa_payment_schedule_report.xml',
        'reports/sa_transfer_deed_report.xml',
        'reports/sa_qr_reports.xml',
        # views
        'views/sa_transfer_tax_views.xml',
        'views/sa_misc_charge_views.xml',
        'views/sa_kibor_rate_views.xml',
        'views/res_partner_views.xml',
        'views/sa_payment_plan_views.xml',
        'views/sa_property_project_views.xml',
        'views/sa_property_views.xml',
        'views/sa_property_dealer_views.xml',
        'views/sa_property_installment_views.xml',
        'views/sa_property_booking_views.xml',
        'views/sa_commission_views.xml',
        'views/sa_property_deal_views.xml',
        'views/sa_property_transfer_views.xml',
        'views/sa_property_document_views.xml',
        'views/sa_property_service_views.xml',
        'views/sa_dealer_allocation_views.xml',
        'views/sa_lead_source_views.xml',
        'views/sa_crm_lead_views.xml',
        'views/sa_verify_templates.xml',
        'views/sa_biometric_verification_views.xml',
        'views/res_config_settings_views.xml',
        'views/sa_property_dashboard_views.xml',
        'views/sa_construction_project_views.xml',
        'views/sa_construction_contract_views.xml',
        'views/sa_construction_ipc_views.xml',
        'views/sa_construction_requisition_views.xml',
        'views/sa_construction_material_issue_views.xml',
        'views/menus.xml',
    ],

    'demo': [
        'demo/demo_data.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'sa_property_management/static/src/scss/sa_property_dashboard.scss',
            'sa_property_management/static/src/js/sa_property_dashboard.js',
            'sa_property_management/static/src/xml/sa_property_dashboard.xml',
            'sa_property_management/static/src/js/sa_fingerprint_field.js',
            'sa_property_management/static/src/xml/sa_fingerprint_field.xml',
        ],
    },

    'images': [
        'static/description/banner.png',
    ],
}
