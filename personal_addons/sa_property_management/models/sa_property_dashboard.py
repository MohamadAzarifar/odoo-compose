# -*- coding: utf-8 -*-
from collections import OrderedDict
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


PROPERTY_STATES = [
    ('draft', 'Draft'),
    ('available', 'Available'),
    ('reserved', 'Reserved'),
    ('booked', 'Booked'),
    ('sold', 'Sold'),
    ('transferred', 'Transferred'),
    ('blocked', 'Blocked'),
]
PROPERTY_STATE_COLORS = {
    'draft': '#9CA3AF',
    'available': '#10B981',
    'reserved': '#F59E0B',
    'booked': '#3B82F6',
    'sold': '#6366F1',
    'transferred': '#8B5CF6',
    'blocked': '#EF4444',
}

PROPERTY_TYPES = [
    ('plot', 'Plot'),
    ('house', 'House'),
    ('apartment', 'Apartment'),
    ('shop', 'Shop'),
    ('commercial', 'Commercial Unit'),
    ('office', 'Office'),
]

BOOKING_STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('in_payment', 'In Payment'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]
BOOKING_STATE_COLORS = {
    'draft': '#9CA3AF',
    'confirmed': '#3B82F6',
    'in_payment': '#F59E0B',
    'completed': '#10B981',
    'cancelled': '#EF4444',
}

INSTALLMENT_STATES = [
    ('pending', 'Pending'),
    ('invoiced', 'Invoiced'),
    ('partial', 'Partially Paid'),
    ('paid', 'Paid'),
    ('overdue', 'Overdue'),
    ('cancelled', 'Cancelled'),
]
INSTALLMENT_STATE_COLORS = {
    'pending': '#9CA3AF',
    'invoiced': '#3B82F6',
    'partial': '#F59E0B',
    'paid': '#10B981',
    'overdue': '#EF4444',
    'cancelled': '#6B7280',
}

TRANSFER_STATES = [
    ('draft', 'Draft'),
    ('in_review', 'In Review'),
    ('approved', 'Approved'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]
TRANSFER_STATE_COLORS = {
    'draft': '#9CA3AF',
    'in_review': '#F59E0B',
    'approved': '#3B82F6',
    'completed': '#10B981',
    'cancelled': '#EF4444',
}


# ----------------------------------------------------------------------
# Customization catalogs
# ----------------------------------------------------------------------
# Selectable KPI tiles for the top strip (key -> label). The front-end owns
# the icon / colour / drill-down for each key; the backend only needs labels.
KPI_CATALOG = [
    ('projects', 'Projects'),
    ('properties', 'Total Properties'),
    ('available', 'Available to Sell'),
    ('reserved', 'Reserved'),
    ('booked', 'Booked'),
    ('sold', 'Sold / Sell-Through'),
    ('active_bookings', 'Active Bookings'),
    ('completed_bookings', 'Completed Bookings'),
    ('transfers_pending', 'Transfers Pending'),
    ('transfers_completed', 'Transfers Completed'),
    ('overdue_count', 'Overdue Installments'),
]

# Toggleable / re-orderable dashboard sections (id -> label).
SECTION_CATALOG = [
    ('financials', 'Financial Summary'),
    ('inventory', 'Inventory Overview'),
    ('sales', 'Sales & Bookings'),
    ('receivables', 'Receivables & Collections'),
    ('recv_compare', 'Receivable vs Received'),
    ('recv_breakdown', 'Receivables Breakdown'),
    ('custom', 'Custom Widgets'),
    ('project_detail', 'Project Inventory Detail'),
    ('lists', 'Upcoming & Top Dealers'),
    ('recent_bookings', 'Recent Bookings'),
    ('transfers', 'Property Transfers'),
]

# Chart types offered by the custom-widget builder.
CHART_TYPES = [
    ('bar', 'Bar'),
    ('line', 'Line'),
    ('doughnut', 'Doughnut'),
    ('pie', 'Pie'),
]

# Whitelisted models + the measures / group-bys a user is allowed to build a
# custom widget from. This is a strict allow-list: anything not listed here is
# rejected, so users can never craft an arbitrary read_group against the DB.
WIDGET_MODELS = OrderedDict([
    ('sa.property.booking', {
        'label': 'Bookings',
        'measures': [
            ('__count', 'Count'),
            ('total_price', 'Total Price'),
            ('amount_paid', 'Collected'),
            ('amount_residual', 'Outstanding'),
        ],
        'groupbys': [
            ('state', 'Status'),
            ('project_id', 'Project'),
            ('booking_date:month', 'Booking Month'),
        ],
    }),
    ('sa.property.installment', {
        'label': 'Installments',
        'measures': [
            ('__count', 'Count'),
            ('amount', 'Amount'),
            ('amount_paid', 'Paid'),
            ('amount_residual', 'Outstanding'),
        ],
        'groupbys': [
            ('state', 'Status'),
            ('due_date:month', 'Due Month'),
        ],
    }),
    ('sa.property', {
        'label': 'Properties',
        'measures': [
            ('__count', 'Count'),
            ('area', 'Area'),
        ],
        'groupbys': [
            ('state', 'Status'),
            ('property_type', 'Type'),
            ('project_id', 'Project'),
        ],
    }),
    ('sa.property.transfer', {
        'label': 'Transfers',
        'measures': [
            ('__count', 'Count'),
            ('sale_price', 'Sale Price'),
            ('total_buyer', 'Buyer Total'),
            ('net_to_seller', 'Net to Seller'),
        ],
        'groupbys': [
            ('state', 'Status'),
            ('project_id', 'Project'),
            ('transfer_date:month', 'Transfer Month'),
        ],
    }),
])


class SaPropertyDashboard(models.AbstractModel):
    _name = 'sa.property.dashboard'
    _description = 'Property Management Dashboard'

    # ------------------------------------------------------------------
    # Public RPC entrypoint
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self, filters=None, custom_widgets=None):
        """Return all KPIs and chart datasets for the dashboard.

        ``filters`` is an optional dict ``{project_ids, date_from, date_to}``
        that scopes every figure. ``custom_widgets`` is the list of user-defined
        widget definitions to compute alongside the built-in charts.
        """
        currency = self.env.company.currency_id
        today = fields.Date.context_today(self)

        return {
            'currency': {
                'symbol': currency.symbol or '',
                'position': currency.position,
                'name': currency.name,
            },
            'today': fields.Date.to_string(today),
            'kpi': self._kpi(today, filters),
            'property_state': self._property_state(filters),
            'property_type': self._property_type(filters),
            'project_inventory': self._project_inventory(filters),
            'booking_state': self._booking_state(filters),
            'booking_trend': self._booking_trend(today, filters),
            'installment_state': self._installment_state(filters),
            'aging': self._aging(today, filters),
            'collection_trend': self._collection_trend(today, filters),
            'receivables_breakdown': self._receivables_breakdown(filters=filters),
            'receivable_vs_received': self._receivable_vs_received_by_project(filters=filters),
            'transfer_state': self._transfer_state(filters),
            'transfer_tax_breakdown': self._transfer_tax_breakdown(filters),
            'transfers_list': self._transfers_list(filters=filters),
            'top_dealers': self._top_dealers(filters=filters),
            'upcoming_installments': self._upcoming_installments(today, filters=filters),
            'recent_bookings': self._recent_bookings(filters=filters),
            'custom_widgets': self._compute_custom_widgets(custom_widgets, filters),
        }

    # ------------------------------------------------------------------
    # Customization: layout persistence + meta
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_bundle(self):
        """One-shot load: effective layout, editor metadata and the data
        computed for that layout's saved filters / custom widgets."""
        layout = self._effective_layout()
        data = self.get_dashboard_data(
            layout.get('filters'), layout.get('custom_widgets'))
        return {
            'is_manager': self.env.user.has_group(
                'sa_property_management.group_sa_property_manager'),
            'meta': self._dashboard_meta(),
            'layout': layout,
            'data': data,
        }

    @api.model
    def save_dashboard_layout(self, layout):
        """Persist the current user's personal layout."""
        clean = self._merge_layout(layout)
        Config = self.env['sa.property.dashboard.config'].sudo()
        rec = Config.search([('user_id', '=', self.env.uid)], limit=1)
        if rec:
            rec.layout = clean
        else:
            Config.create({'user_id': self.env.uid, 'layout': clean})
        return clean

    @api.model
    def reset_dashboard_layout(self):
        """Drop the user's personal layout and fall back to default/built-in."""
        Config = self.env['sa.property.dashboard.config'].sudo()
        Config.search([('user_id', '=', self.env.uid)]).unlink()
        return self._effective_layout()

    @api.model
    def save_dashboard_default(self, layout):
        """Manager-only: store the company-wide default layout."""
        if not self.env.user.has_group(
                'sa_property_management.group_sa_property_manager'):
            raise AccessError(_(
                "Only Property Managers can set the company default dashboard."))
        clean = self._merge_layout(layout)
        Config = self.env['sa.property.dashboard.config'].sudo()
        rec = Config.search([('is_default', '=', True)], limit=1)
        if rec:
            rec.layout = clean
        else:
            Config.create({'is_default': True, 'layout': clean})
        return clean

    def _default_layout(self):
        return {
            'kpis': ['projects', 'properties', 'available',
                     'reserved', 'sold', 'active_bookings'],
            'sections': [{'id': sid, 'visible': True} for sid, _l in SECTION_CATALOG],
            'filters': {'project_ids': [], 'date_from': False, 'date_to': False},
            'custom_widgets': [],
        }

    def _effective_layout(self):
        Config = self.env['sa.property.dashboard.config'].sudo()
        rec = Config.search([('user_id', '=', self.env.uid)], limit=1)
        if rec and rec.layout:
            return self._merge_layout(rec.layout)
        default = Config.search([('is_default', '=', True)], limit=1)
        if default and default.layout:
            return self._merge_layout(default.layout)
        return self._default_layout()

    def _merge_layout(self, stored):
        """Reconcile a stored layout against the current catalogs so newly
        added sections/KPIs still surface and removed ones are dropped."""
        base = self._default_layout()
        merged = dict(base)
        if not isinstance(stored, dict):
            return merged

        valid_kpis = {k for k, _l in KPI_CATALOG}
        if isinstance(stored.get('kpis'), list):
            kept = [k for k in stored['kpis'] if k in valid_kpis]
            merged['kpis'] = kept or base['kpis']

        valid_sections = {s for s, _l in SECTION_CATALOG}
        if isinstance(stored.get('sections'), list):
            seen, sections = [], []
            for s in stored['sections']:
                sid = s.get('id') if isinstance(s, dict) else None
                if sid in valid_sections and sid not in seen:
                    sections.append({'id': sid, 'visible': bool(s.get('visible', True))})
                    seen.append(sid)
            for sid, _l in SECTION_CATALOG:
                if sid not in seen:
                    sections.append({'id': sid, 'visible': True})
            merged['sections'] = sections

        if isinstance(stored.get('filters'), dict):
            f = stored['filters']
            pids = []
            for x in (f.get('project_ids') or []):
                try:
                    pids.append(int(x))
                except (TypeError, ValueError):
                    continue
            merged['filters'] = {
                'project_ids': pids,
                'date_from': f.get('date_from') or False,
                'date_to': f.get('date_to') or False,
            }

        if isinstance(stored.get('custom_widgets'), list):
            widgets = []
            for w in stored['custom_widgets'][:12]:
                if isinstance(w, dict) and w.get('model') in WIDGET_MODELS:
                    widgets.append({
                        'id': str(w.get('id') or ''),
                        'title': (w.get('title') or '')[:80],
                        'model': w.get('model'),
                        'measure': w.get('measure') or '__count',
                        'group_by': w.get('group_by'),
                        'chart': w.get('chart') or 'bar',
                    })
            merged['custom_widgets'] = widgets

        return merged

    def _dashboard_meta(self):
        return {
            'kpi_catalog': [{'key': k, 'label': l} for k, l in KPI_CATALOG],
            'section_catalog': [{'id': s, 'label': l} for s, l in SECTION_CATALOG],
            'chart_types': [{'value': v, 'label': l} for v, l in CHART_TYPES],
            'widget_models': [
                {
                    'model': m,
                    'label': spec['label'],
                    'measures': [{'value': mv, 'label': ml} for mv, ml in spec['measures']],
                    'groupbys': [{'value': gv, 'label': gl} for gv, gl in spec['groupbys']],
                }
                for m, spec in WIDGET_MODELS.items()
            ],
            'projects': self._filter_options(),
        }

    def _filter_options(self):
        projects = self.env['sa.property.project'].search([], order='name')
        return [{'id': p.id, 'name': p.name or p.code} for p in projects]

    # ------------------------------------------------------------------
    # Filter domain helpers
    # ------------------------------------------------------------------
    def _f(self, filters):
        filters = filters or {}
        return (
            filters.get('project_ids') or [],
            filters.get('date_from') or False,
            filters.get('date_to') or False,
        )

    def _dom_property(self, filters):
        pids = self._f(filters)[0]
        return [('project_id', 'in', pids)] if pids else []

    def _dom_booking(self, filters):
        pids, df, dt = self._f(filters)
        dom = []
        if pids:
            dom.append(('project_id', 'in', pids))
        if df:
            dom.append(('booking_date', '>=', df))
        if dt:
            dom.append(('booking_date', '<=', dt))
        return dom

    def _dom_inst_proj(self, filters):
        pids = self._f(filters)[0]
        return [('property_id.project_id', 'in', pids)] if pids else []

    def _dom_installment(self, filters):
        pids, df, dt = self._f(filters)
        dom = []
        if pids:
            dom.append(('property_id.project_id', 'in', pids))
        if df:
            dom.append(('due_date', '>=', df))
        if dt:
            dom.append(('due_date', '<=', dt))
        return dom

    def _dom_transfer(self, filters):
        pids, df, dt = self._f(filters)
        dom = []
        if pids:
            dom.append(('project_id', 'in', pids))
        if df:
            dom.append(('transfer_date', '>=', df))
        if dt:
            dom.append(('transfer_date', '<=', dt))
        return dom

    # ------------------------------------------------------------------
    # Custom widgets
    # ------------------------------------------------------------------
    def _compute_custom_widgets(self, custom_widgets, filters):
        out = []
        for w in (custom_widgets or []):
            if not isinstance(w, dict):
                continue
            res = self._compute_custom_widget(w, filters)
            if res:
                out.append(res)
        return out

    def _widget_domain(self, model, filters):
        pids = self._f(filters)[0]
        if not pids:
            return []
        if model == 'sa.property.installment':
            return [('property_id.project_id', 'in', pids)]
        if model in ('sa.property.booking', 'sa.property.transfer', 'sa.property'):
            return [('project_id', 'in', pids)]
        return []

    def _fmt_group_key(self, model, group_by, key):
        if key is False or key is None:
            return 'Undefined'
        if hasattr(key, 'display_name'):
            return key.display_name or 'Undefined'
        field_name = group_by.split(':')[0]
        field = self.env[model]._fields.get(field_name)
        if field and field.type == 'selection':
            mapping = dict(field._description_selection(self.env))
            return mapping.get(key, str(key))
        return str(key)

    def _compute_custom_widget(self, widget, filters):
        model = widget.get('model')
        spec = WIDGET_MODELS.get(model)
        if not spec:
            return None
        measure = widget.get('measure') or '__count'
        group_by = widget.get('group_by')
        valid_measures = {m for m, _l in spec['measures']}
        valid_groupbys = {g for g, _l in spec['groupbys']}
        if measure not in valid_measures or group_by not in valid_groupbys:
            return None

        Model = self.env[model]
        agg = '__count' if measure == '__count' else '%s:sum' % measure
        try:
            grouped = Model._read_group(
                domain=self._widget_domain(model, filters),
                groupby=[group_by],
                aggregates=[agg],
            )
        except Exception:
            return None

        labels, values = [], []
        for row in grouped:
            labels.append(self._fmt_group_key(model, group_by, row[0]))
            values.append(row[1] or 0)

        measure_label = dict(spec['measures']).get(measure, measure)
        return {
            'id': str(widget.get('id') or ''),
            'title': widget.get('title') or '%s by %s' % (spec['label'], group_by),
            'chart': widget.get('chart') or 'bar',
            'measure_label': measure_label,
            'labels': labels,
            'values': values,
        }


    # ------------------------------------------------------------------
    # KPI cards
    # ------------------------------------------------------------------
    def _kpi(self, today, filters=None):
        Property = self.env['sa.property']
        Booking = self.env['sa.property.booking']
        Installment = self.env['sa.property.installment']
        Transfer = self.env['sa.property.transfer']
        Project = self.env['sa.property.project']

        pdom = self._dom_property(filters)
        bdom = self._dom_booking(filters)
        idom = self._dom_inst_proj(filters)
        tdom = self._dom_transfer(filters)
        pids = self._f(filters)[0]

        # Counts
        projects = Project.search_count([('id', 'in', pids)] if pids else [])
        properties = Property.search_count(pdom)
        available = Property.search_count(pdom + [('state', '=', 'available')])
        reserved = Property.search_count(pdom + [('state', '=', 'reserved')])
        booked = Property.search_count(pdom + [('state', '=', 'booked')])
        sold = Property.search_count(pdom + [('state', 'in', ('sold', 'transferred'))])

        active_bookings = Booking.search_count(
            bdom + [('state', 'in', ('confirmed', 'in_payment'))])
        completed_bookings = Booking.search_count(bdom + [('state', '=', 'completed')])

        # Money — aggregate from non-cancelled bookings
        all_bookings = Booking.search(bdom + [('state', '!=', 'cancelled')])
        sales_value = sum(all_bookings.mapped('total_price'))
        invoiced = sum(all_bookings.mapped('amount_invoiced'))
        collected = sum(all_bookings.mapped('amount_paid'))
        outstanding = sum(all_bookings.mapped('amount_residual'))

        overdue = Installment.search(idom + [('state', '=', 'overdue')])
        overdue_amount = sum(overdue.mapped('amount_residual'))

        next_7 = Installment.search_count(idom + [
            ('state', 'in', ('pending', 'invoiced', 'partial')),
            ('due_date', '>=', today),
            ('due_date', '<=', today + relativedelta(days=7)),
        ])
        next_30 = Installment.search_count(idom + [
            ('state', 'in', ('pending', 'invoiced', 'partial')),
            ('due_date', '>=', today),
            ('due_date', '<=', today + relativedelta(days=30)),
        ])

        transfers_pending = Transfer.search_count(
            tdom + [('state', 'in', ('draft', 'in_review', 'approved'))])
        transfers_completed = Transfer.search_count(
            tdom + [('state', '=', 'completed')])

        sell_through = (sold / properties * 100.0) if properties else 0.0

        return {
            'projects': projects,
            'properties': properties,
            'available': available,
            'reserved': reserved,
            'booked': booked,
            'sold': sold,
            'sell_through': round(sell_through, 1),
            'active_bookings': active_bookings,
            'completed_bookings': completed_bookings,
            'sales_value': sales_value,
            'invoiced': invoiced,
            'collected': collected,
            'outstanding': outstanding,
            'collection_rate': round((collected / invoiced * 100.0) if invoiced else 0.0, 1),
            'overdue_count': len(overdue),
            'overdue_amount': overdue_amount,
            'due_next_7': next_7,
            'due_next_30': next_30,
            'transfers_pending': transfers_pending,
            'transfers_completed': transfers_completed,
        }

    # ------------------------------------------------------------------
    # Property charts
    # ------------------------------------------------------------------
    def _property_state(self, filters=None):
        data = self.env['sa.property']._read_group(
            domain=self._dom_property(filters),
            groupby=['state'],
            aggregates=['__count'],
        )
        label_map = dict(PROPERTY_STATES)
        rows = []
        for state, count in data:
            rows.append({
                'key': state,
                'label': label_map.get(state, state),
                'value': count,
                'color': PROPERTY_STATE_COLORS.get(state, '#9CA3AF'),
            })
        return rows

    def _property_type(self, filters=None):
        data = self.env['sa.property']._read_group(
            domain=self._dom_property(filters),
            groupby=['property_type'],
            aggregates=['__count'],
        )
        label_map = dict(PROPERTY_TYPES)
        return [
            {'key': t, 'label': label_map.get(t, t), 'value': c}
            for t, c in data
        ]

    def _project_inventory(self, filters=None):
        """Per-project: total / available / reserved / booked / sold + sell-through %."""
        Property = self.env['sa.property']
        Project = self.env['sa.property.project']
        pids = self._f(filters)[0]
        projects = Project.search([('id', 'in', pids)] if pids else [])
        # Group properties per project per state in one shot
        grouped = Property._read_group(
            domain=[('project_id', 'in', projects.ids)],
            groupby=['project_id', 'state'],
            aggregates=['__count'],
        )
        # Build {project_id: {state: count}}
        per_project = {p.id: {s: 0 for s, _l in PROPERTY_STATES} for p in projects}
        for project, state, count in grouped:
            per_project[project.id][state] = count

        rows = []
        for project in projects:
            states = per_project[project.id]
            total = sum(states.values())
            sold = states.get('sold', 0) + states.get('transferred', 0)
            rows.append({
                'id': project.id,
                'name': project.name,
                'code': project.code,
                'total': total,
                'available': states.get('available', 0),
                'reserved': states.get('reserved', 0),
                'booked': states.get('booked', 0),
                'sold': sold,
                'blocked': states.get('blocked', 0),
                'sell_through': round((sold / total * 100.0) if total else 0.0, 1),
            })
        # Largest projects first
        rows.sort(key=lambda r: r['total'], reverse=True)
        return rows

    # ------------------------------------------------------------------
    # Booking charts
    # ------------------------------------------------------------------
    def _booking_state(self, filters=None):
        data = self.env['sa.property.booking']._read_group(
            domain=self._dom_booking(filters),
            groupby=['state'],
            aggregates=['__count', 'total_price:sum'],
        )
        label_map = dict(BOOKING_STATES)
        return [
            {
                'key': state,
                'label': label_map.get(state, state),
                'value': count,
                'amount': amount or 0.0,
                'color': BOOKING_STATE_COLORS.get(state, '#9CA3AF'),
            }
            for state, count, amount in data
        ]

    def _booking_trend(self, today, filters=None):
        """Last 12 months — confirmed/in_payment/completed booking count & value."""
        start = (today.replace(day=1) - relativedelta(months=11))
        pids = self._f(filters)[0]
        domain = ([('project_id', 'in', pids)] if pids else []) + [
            ('booking_date', '>=', start),
            ('state', '!=', 'cancelled'),
        ]
        bookings = self.env['sa.property.booking'].search(domain)
        buckets = OrderedDict()
        cursor = start
        for _i in range(12):
            buckets[cursor.strftime('%Y-%m')] = {
                'label': cursor.strftime('%b %y'),
                'count': 0,
                'value': 0.0,
            }
            cursor = cursor + relativedelta(months=1)
        for b in bookings:
            key = b.booking_date.strftime('%Y-%m')
            if key in buckets:
                buckets[key]['count'] += 1
                buckets[key]['value'] += b.total_price
        return list(buckets.values())

    # ------------------------------------------------------------------
    # Installment / receivables
    # ------------------------------------------------------------------
    def _installment_state(self, filters=None):
        data = self.env['sa.property.installment']._read_group(
            domain=self._dom_inst_proj(filters),
            groupby=['state'],
            aggregates=['__count', 'amount:sum', 'amount_residual:sum'],
        )
        label_map = dict(INSTALLMENT_STATES)
        return [
            {
                'key': state,
                'label': label_map.get(state, state),
                'value': count,
                'amount': amount or 0.0,
                'residual': residual or 0.0,
                'color': INSTALLMENT_STATE_COLORS.get(state, '#9CA3AF'),
            }
            for state, count, amount, residual in data
        ]

    def _aging(self, today, filters=None):
        """Overdue installments grouped into aging buckets."""
        buckets = [
            ('0-30',   1,  30,  '#FBBF24'),
            ('31-60',  31, 60,  '#FB923C'),
            ('61-90',  61, 90,  '#F87171'),
            ('90+',    91, 99999, '#DC2626'),
        ]
        overdue = self.env['sa.property.installment'].search(
            self._dom_inst_proj(filters) + [('state', '=', 'overdue')])
        rows = []
        for label, lo, hi, color in buckets:
            inst = overdue.filtered(lambda i: lo <= i.days_overdue <= hi)
            rows.append({
                'label': label,
                'count': len(inst),
                'amount': sum(inst.mapped('amount_residual')),
                'color': color,
            })
        return rows

    def _collection_trend(self, today, filters=None):
        """Last 12 months — installments due vs collected (by due_date)."""
        start = (today.replace(day=1) - relativedelta(months=11))
        installments = self.env['sa.property.installment'].search(
            self._dom_inst_proj(filters) + [
                ('due_date', '>=', start),
                ('state', '!=', 'cancelled'),
            ])
        buckets = OrderedDict()
        cursor = start
        for _i in range(12):
            buckets[cursor.strftime('%Y-%m')] = {
                'label': cursor.strftime('%b %y'),
                'due': 0.0,
                'collected': 0.0,
            }
            cursor = cursor + relativedelta(months=1)
        for i in installments:
            key = i.due_date.strftime('%Y-%m')
            if key in buckets:
                buckets[key]['due'] += i.amount
                buckets[key]['collected'] += i.amount_paid
        return list(buckets.values())

    # ------------------------------------------------------------------
    # Receivables breakdown — block / project / sector / floor wise
    # ------------------------------------------------------------------
    def _receivables_breakdown(self, limit=12, filters=None):
        """Aggregate billed / received / outstanding receivables across the
        location dimensions that actually carry data: project, block, floor and
        sector (project city). Dimensions with no usable value are skipped so
        only *applicable* breakdowns are surfaced on the dashboard."""
        Installment = self.env['sa.property.installment']
        grouped = Installment._read_group(
            domain=self._dom_inst_proj(filters) + [('state', '!=', 'cancelled')],
            groupby=['property_id'],
            aggregates=['amount:sum', 'amount_paid:sum',
                        'amount_residual:sum', '__count'],
        )

        prop_ids = [prop.id for prop, *_rest in grouped if prop]
        props = {p.id: p for p in self.env['sa.property'].browse(prop_ids)}

        dims = {
            'project': OrderedDict(),
            'block': OrderedDict(),
            'sector': OrderedDict(),
            'floor': OrderedDict(),
        }

        def _bump(bucket, key, label, total, received, outstanding, count):
            if not key:
                return
            row = bucket.get(key)
            if not row:
                row = {
                    'key': key,
                    'label': label,
                    'total': 0.0,
                    'received': 0.0,
                    'outstanding': 0.0,
                    'count': 0,
                }
                bucket[key] = row
            row['total'] += total
            row['received'] += received
            row['outstanding'] += outstanding
            row['count'] += count

        for prop, total, paid, residual, count in grouped:
            if not prop:
                continue
            p = props.get(prop.id)
            if not p:
                continue
            total = total or 0.0
            paid = paid or 0.0
            residual = residual or 0.0
            project = p.project_id
            _bump(dims['project'],
                  project.id if project else None,
                  (project.name or project.code) if project else None,
                  total, paid, residual, count)
            _bump(dims['block'], p.block, p.block, total, paid, residual, count)
            _bump(dims['floor'], p.floor, p.floor, total, paid, residual, count)
            sector = project.city if project else None
            _bump(dims['sector'], sector, sector, total, paid, residual, count)

        def _finalize(bucket):
            rows = list(bucket.values())
            for r in rows:
                r['collection_rate'] = round(
                    (r['received'] / r['total'] * 100.0) if r['total'] else 0.0, 1)
            rows.sort(key=lambda r: r['total'], reverse=True)
            return rows[:limit]

        return {
            'project': _finalize(dims['project']),
            'block': _finalize(dims['block']),
            'sector': _finalize(dims['sector']),
            'floor': _finalize(dims['floor']),
        }

    def _receivable_vs_received_by_project(self, limit=10, filters=None):
        """Per-project receivable (outstanding) vs received (collected) for the
        comparison chart."""
        breakdown = self._receivables_breakdown(limit=limit, filters=filters)
        return [
            {
                'label': r['label'],
                'received': r['received'],
                'receivable': r['outstanding'],
                'total': r['total'],
            }
            for r in breakdown['project']
        ]

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------
    def _transfer_state(self, filters=None):
        data = self.env['sa.property.transfer']._read_group(
            domain=self._dom_transfer(filters),
            groupby=['state'],
            aggregates=['__count', 'sale_price:sum'],
        )
        label_map = dict(TRANSFER_STATES)
        return [
            {
                'key': state,
                'label': label_map.get(state, state),
                'value': count,
                'amount': amount or 0.0,
                'color': TRANSFER_STATE_COLORS.get(state, '#9CA3AF'),
            }
            for state, count, amount in data
        ]

    def _transfer_tax_breakdown(self, filters=None):
        """Total tax amount per tax type (across all transfers)."""
        pids = self._f(filters)[0]
        tdom = [('transfer_id.project_id', 'in', pids)] if pids else []
        data = self.env['sa.transfer.tax.line']._read_group(
            domain=tdom + [('transfer_id.state', '!=', 'cancelled')],
            groupby=['tax_id'],
            aggregates=['amount:sum'],
        )
        rows = [
            {'label': tax.name, 'amount': amount or 0.0}
            for tax, amount in data
        ]
        rows.sort(key=lambda r: r['amount'], reverse=True)
        return rows

    def _transfers_list(self, limit=12, filters=None):
        """Most recent property transfers for the dashboard list."""
        transfers = self.env['sa.property.transfer'].search(
            self._dom_transfer(filters), order='transfer_date desc, id desc', limit=limit)
        label_map = dict(TRANSFER_STATES)
        return [
            {
                'id': t.id,
                'name': t.name,
                'date': fields.Date.to_string(t.transfer_date) if t.transfer_date else '',
                'property': t.property_id.display_name or '',
                'project': t.project_id.name or '',
                'from_partner': t.from_partner_id.name or '',
                'to_partner': t.to_partner_id.name or '',
                'sale_price': t.sale_price,
                'total_buyer': t.total_buyer,
                'net_to_seller': t.net_to_seller,
                'state': t.state,
                'state_label': label_map.get(t.state, t.state),
                'state_color': TRANSFER_STATE_COLORS.get(t.state, '#9CA3AF'),
            }
            for t in transfers
        ]

    # ------------------------------------------------------------------
    # Dealers & lists
    # ------------------------------------------------------------------
    def _top_dealers(self, limit=5, filters=None):
        pids = self._f(filters)[0]
        dealers = self.env['sa.property.dealer'].search([])
        rows = []
        for d in dealers:
            active = d.booking_ids.filtered(lambda b: b.state != 'cancelled')
            if pids:
                active = active.filtered(lambda b: b.project_id.id in pids)
            rows.append({
                'id': d.id,
                'name': d.name or d.code,
                'bookings': len(active),
                'sales': sum(active.mapped('total_price')),
                'commission': sum(active.mapped('commission_amount')),
            })
        rows.sort(key=lambda r: r['sales'], reverse=True)
        return rows[:limit]

    def _upcoming_installments(self, today, limit=10, filters=None):
        upcoming = self.env['sa.property.installment'].search(
            self._dom_inst_proj(filters) + [
                ('state', 'in', ('pending', 'invoiced', 'partial')),
                ('due_date', '>=', today),
                ('due_date', '<=', today + relativedelta(days=30)),
            ], order='due_date asc', limit=limit)
        return [
            {
                'id': i.id,
                'booking_id': i.booking_id.id,
                'booking': i.booking_id.name,
                'customer': i.booking_id.customer_id.name or '',
                'property': i.booking_id.property_id.display_name or '',
                'due_date': fields.Date.to_string(i.due_date),
                'days_to_due': (i.due_date - today).days,
                'amount': i.amount_residual,
                'state': i.state,
            }
            for i in upcoming
        ]

    def _recent_bookings(self, limit=8, filters=None):
        bookings = self.env['sa.property.booking'].search(
            self._dom_booking(filters), order='booking_date desc, id desc', limit=limit)
        label_map = dict(BOOKING_STATES)
        return [
            {
                'id': b.id,
                'name': b.name,
                'customer': b.customer_id.name or '',
                'property': b.property_id.display_name or '',
                'project': b.project_id.name or '',
                'date': fields.Date.to_string(b.booking_date),
                'amount': b.total_price,
                'collected': b.amount_paid,
                'outstanding': b.amount_residual,
                'state': b.state,
                'state_label': label_map.get(b.state, b.state),
                'state_color': BOOKING_STATE_COLORS.get(b.state, '#9CA3AF'),
            }
            for b in bookings
        ]
