# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# Conversion factors of each supported area unit into square feet. Values use
# the traditional Pakistani land standard (1 Marla = 272.25 sq ft, 1 Kanal =
# 20 Marla). These let us aggregate mixed-unit properties under one project.
SA_AREA_SQFT_FACTORS = {
    'marla': 272.25,
    'kanal': 5445.0,
    'sqft': 1.0,
    'sqyd': 9.0,
    'sqm': 10.7639,
    'acre': 43560.0,
}


def sa_convert_area(value, from_uom, to_uom):
    """Convert an area ``value`` from ``from_uom`` to ``to_uom`` via sq ft."""
    if not value or from_uom not in SA_AREA_SQFT_FACTORS \
            or to_uom not in SA_AREA_SQFT_FACTORS:
        return value or 0.0
    return value * SA_AREA_SQFT_FACTORS[from_uom] / SA_AREA_SQFT_FACTORS[to_uom]


class SaPropertyFeature(models.Model):
    _name = 'sa.property.feature'
    _description = 'Property Feature'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    color = fields.Integer()

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Feature name must be unique.'),
    ]


class SaProperty(models.Model):
    """An individual property unit — plot, apartment, house or commercial unit."""
    _name = 'sa.property'
    _description = 'Property Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'sa.qr.mixin',
                'sa.image.optimize.mixin']
    _order = 'project_id, code'
    _rec_name = 'display_name'

    _sa_doc_type = _('Property File')
    _sa_image_fields = ('image',)

    name = fields.Char(string='Title', required=True, tracking=True)
    code = fields.Char(string='Reference', required=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Pricing currency for this unit. Defaults from the project.")

    project_id = fields.Many2one(
        'sa.property.project', string='Project', required=True,
        ondelete='restrict', tracking=True, index=True)

    property_type = fields.Selection(
        [('plot', 'Plot'),
         ('house', 'House'),
         ('apartment', 'Apartment'),
         ('shop', 'Shop'),
         ('commercial', 'Commercial Unit'),
         ('office', 'Office')],
        default='plot', required=True, tracking=True)

    # Pakistani location detail
    block = fields.Char(tracking=True)
    street = fields.Char()
    plot_number = fields.Char(tracking=True)
    floor = fields.Char()
    facing = fields.Selection(
        [('north', 'North'),
         ('south', 'South'),
         ('east', 'East'),
         ('west', 'West'),
         ('north_east', 'North-East'),
         ('north_west', 'North-West'),
         ('south_east', 'South-East'),
         ('south_west', 'South-West')])
    location_premium = fields.Selection(
        [('none', 'None'),
         ('corner', 'Corner'),
         ('park_facing', 'Park-Facing'),
         ('main_road', 'Main Road'),
         ('main_boulevard', 'Main Boulevard'),
         ('corner_park', 'Corner + Park-Facing')],
        default='none')

    area = fields.Float(string='Area', required=True, tracking=True)
    area_uom = fields.Selection(
        [('marla', 'Marla'),
         ('kanal', 'Kanal'),
         ('sqft', 'Square Foot'),
         ('sqyd', 'Square Yard'),
         ('sqm', 'Square Meter'),
         ('acre', 'Acre')],
        required=True, default='marla', tracking=True)
    covered_area = fields.Float(string='Covered Area (Sq.Ft)')

    bedrooms = fields.Integer()
    bathrooms = fields.Integer()
    parking_spaces = fields.Integer()
    feature_ids = fields.Many2many('sa.property.feature', string='Features')

    base_price = fields.Monetary(currency_field='currency_id', tracking=True)
    price_per_unit_area = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_price_per_unit_area', store=True)
    dc_value = fields.Monetary(
        currency_field='currency_id',
        help="DC (Deputy Commissioner) notified value used for FBR/CVT tax base.")

    # --- Product / Inventory integration ---
    product_tmpl_id = fields.Many2one(
        'product.template', string='Product', copy=False, readonly=True,
        ondelete='restrict',
        help="Linked storable product so this unit appears in the standard "
             "Products, Sales, Purchase and Inventory apps.")
    product_id = fields.Many2one(
        'product.product', string='Product Variant', copy=False,
        compute='_compute_product_id', store=True)
    qty_on_hand = fields.Float(
        string='On Hand', related='product_id.qty_available', readonly=True)
    deal_id = fields.Many2one(
        'sa.property.deal', string='Investor Deal', copy=False, index=True,
        ondelete='set null', tracking=True,
        help="Investor deal this unit is allocated to, if any.")

    image = fields.Image(max_width=1920, max_height=1920)
    description = fields.Html()

    image_ids = fields.One2many(
        'sa.property.image', 'property_id', string='Gallery')
    collateral_ids = fields.One2many(
        'sa.marketing.collateral', 'property_id', string='Marketing Collateral')
    service_assignment_ids = fields.One2many(
        'sa.property.service.assignment', 'property_id', string='Service Billing')

    state = fields.Selection(
        [('draft', 'Draft'),
         ('available', 'Available'),
         ('reserved', 'Reserved'),
         ('booked', 'Booked'),
         ('sold', 'Sold'),
         ('transferred', 'Transferred'),
         ('blocked', 'Blocked')],
        default='draft', required=True, tracking=True, copy=False)

    current_owner_id = fields.Many2one(
        'res.partner', string='Current Owner', tracking=True, copy=False)
    booking_ids = fields.One2many(
        'sa.property.booking', 'property_id', string='Bookings')
    booking_count = fields.Integer(
        compute='_compute_counts', store=False)
    transfer_ids = fields.One2many(
        'sa.property.transfer', 'property_id', string='Transfers')
    transfer_count = fields.Integer(
        compute='_compute_counts', store=False)
    document_ids = fields.One2many(
        'sa.property.document', 'property_id', string='Documents')
    document_count = fields.Integer(
        compute='_compute_counts', store=False)

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Property reference must be unique per company.'),
        ('area_positive', 'CHECK(area > 0)', 'Area must be greater than zero.'),
        ('base_price_positive', 'CHECK(base_price >= 0)',
         'Base price cannot be negative.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'sa.property') or _('New')
        records = super().create(vals_list)
        for rec in records:
            rec._sync_product()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('sa_skip_product_sync') and any(
                f in vals for f in ('name', 'code', 'project_id', 'base_price')):
            self.with_context(sa_skip_product_sync=True)._sync_product()
        return res

    @api.depends('product_tmpl_id')
    def _compute_product_id(self):
        for rec in self:
            rec.product_id = (
                rec.product_tmpl_id.product_variant_id.id
                if rec.product_tmpl_id else False)

    # ------------------------------------------------------------------
    # Product / Inventory integration
    # ------------------------------------------------------------------
    def _prepare_product_vals(self):
        """Values used to create or update the linked storable product."""
        self.ensure_one()
        categ = self.env.ref(
            'sa_property_management.product_category_property',
            raise_if_not_found=False)
        code = self.code if self.code and self.code != _('New') else False
        vals = {
            'name': self.display_name or self.name or _('Property'),
            'type': 'consu',
            'is_storable': True,
            'sale_ok': True,
            'purchase_ok': True,
            'list_price': self.base_price or 0.0,
            'default_code': code,
            'company_id': self.company_id.id,
            'sa_property_id': self.id,
            # Invoicing is owned by the booking's installment schedule, not the
            # sale order. A delivery policy keeps the order from prompting its
            # own (duplicate) invoice during the payment lifecycle.
            'invoice_policy': 'delivery',
        }
        if categ:
            vals['categ_id'] = categ.id
        return vals

    def _sync_product(self):
        """Create the linked product the first time, then keep key fields in sync."""
        Product = self.env['product.template']
        for rec in self:
            vals = rec._prepare_product_vals()
            if rec.product_tmpl_id:
                rec.product_tmpl_id.write({
                    'name': vals['name'],
                    'list_price': vals['list_price'],
                    'default_code': vals['default_code'],
                    'invoice_policy': 'delivery',
                })
            else:
                tmpl = Product.create(vals)
                rec.with_context(sa_skip_product_sync=True).product_tmpl_id = tmpl.id
                rec._sa_set_on_hand(1.0)

    def _sa_set_on_hand(self, qty):
        """Set the on-hand quantity of the linked storable product."""
        self.ensure_one()
        product = self.product_tmpl_id.product_variant_id
        if not product or not self.product_tmpl_id.is_storable:
            return
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not warehouse:
            return
        quant = self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': warehouse.lot_stock_id.id,
            'inventory_quantity': qty,
        })
        quant.action_apply_inventory()

    @api.depends('name', 'code', 'project_id')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.code or '', rec.name or '']
            rec.display_name = ' - '.join(p for p in parts if p)

    @api.onchange('project_id')
    def _onchange_project_id_currency(self):
        if self.project_id and self.project_id.currency_id:
            self.currency_id = self.project_id.currency_id

    def _sa_status_info(self):
        self.ensure_one()
        labels = dict(self._fields['state'].selection)
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.display_name,
            'status': self.state,
            'status_label': labels.get(self.state, self.state),
            'valid': self.state not in ('blocked', 'draft'),
            'rows': [
                (_('Project'), self.project_id.name or ''),
                (_('Type'), dict(self._fields['property_type'].selection).get(
                    self.property_type, '')),
                (_('Area'), '%s %s' % (
                    self.area or 0.0,
                    dict(self._fields['area_uom'].selection).get(self.area_uom, ''))),
                (_('Current Owner'), self.current_owner_id.name or _('—')),
            ],
        }

    @api.depends('base_price', 'area')
    def _compute_price_per_unit_area(self):
        for rec in self:
            rec.price_per_unit_area = (
                rec.base_price / rec.area if rec.area else 0.0)

    def _sa_area_in(self, target_uom):
        """Return this property's area converted to ``target_uom``."""
        self.ensure_one()
        return sa_convert_area(self.area, self.area_uom, target_uom)

    @api.constrains('area', 'area_uom', 'project_id')
    def _check_project_area_limit(self):
        for project in self.mapped('project_id'):
            if not project or not project.enforce_area_limit \
                    or not project.total_area:
                continue
            consumed = project._sa_consumed_area()
            # Tiny tolerance to absorb floating-point conversion noise.
            if consumed > project.total_area + 1e-4:
                uom_label = dict(
                    project._fields['area_uom'].selection).get(
                        project.area_uom, project.area_uom)
                raise ValidationError(_(
                    "Cannot add this property to project '%(project)s': the "
                    "combined area of its properties (%(consumed).2f %(uom)s) "
                    "would exceed the project's total land area "
                    "(%(total).2f %(uom)s).\n\nDisable 'Enforce Land-Area "
                    "Limit' on the project to allow this.",
                    project=project.name,
                    consumed=consumed,
                    total=project.total_area,
                    uom=uom_label))

    @api.depends('booking_ids', 'transfer_ids', 'document_ids')
    def _compute_counts(self):
        for rec in self:
            rec.booking_count = len(rec.booking_ids)
            rec.transfer_count = len(rec.transfer_ids)
            rec.document_count = len(rec.document_ids)

    @api.constrains('state', 'current_owner_id')
    def _check_owner_required(self):
        for rec in self:
            if rec.state in ('sold', 'transferred') and not rec.current_owner_id:
                raise ValidationError(_(
                    "Property '%s' is %s but has no owner set."
                ) % (rec.display_name, rec.state))

    def action_set_available(self):
        for rec in self:
            if rec.state in ('booked', 'sold', 'transferred'):
                raise ValidationError(_(
                    "Cannot mark '%s' available: it is currently %s."
                ) % (rec.display_name, rec.state))
            rec.state = 'available'

    def action_block(self):
        for rec in self:
            if rec.state in ('booked', 'sold', 'transferred'):
                raise ValidationError(_(
                    "Cannot block '%s' while it is %s."
                ) % (rec.display_name, rec.state))
            rec.state = 'blocked'

    def action_unblock(self):
        for rec in self:
            if rec.state != 'blocked':
                raise ValidationError(_(
                    "Only blocked units can be unblocked. '%s' is %s."
                ) % (rec.display_name, rec.state))
            rec.state = 'available'

    def action_open_buyback_wizard(self):
        self.ensure_one()
        if self.state not in ('sold', 'transferred'):
            raise ValidationError(_(
                "Buy-back applies to sold or transferred units only. "
                "'%s' is %s."
            ) % (self.display_name, self.state))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Buy Back - %s', self.display_name),
            'res_model': 'sa.property.buyback.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_property_id': self.id},
        }

    def action_open_surrender_wizard(self):
        self.ensure_one()
        if self.state != 'booked':
            raise ValidationError(_(
                "Surrender applies to booked units only. '%s' is %s."
            ) % (self.display_name, self.state))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Surrender - %s', self.display_name),
            'res_model': 'sa.property.surrender.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_property_id': self.id},
        }

    def _reset_to_available(self, restock=True):
        """Return a unit to the available pool, clearing ownership.

        Used by the buy-back and surrender flows. When ``restock`` is set the
        linked storable product's on-hand quantity is brought back to one so
        the unit is sellable again through the standard Inventory flow.
        """
        for rec in self:
            rec.state = 'available'
            rec.current_owner_id = False
            if restock and rec.product_tmpl_id and rec.qty_on_hand < 1.0:
                rec._sa_set_on_hand(1.0)

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings - %s', self.display_name),
            'res_model': 'sa.property.booking',
            'view_mode': 'list,form',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id},
        }

    def action_view_transfers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfers - %s', self.display_name),
            'res_model': 'sa.property.transfer',
            'view_mode': 'list,form',
            'domain': [('property_id', '=', self.id)],
            'context': {'default_property_id': self.id},
        }

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents - %s', self.display_name),
            'res_model': 'sa.property.document',
            'view_mode': 'list,form',
            'domain': [('property_id', '=', self.id)],
            'context': {
                'default_property_id': self.id,
                'default_partner_id': self.current_owner_id.id,
            },
        }

    def action_view_product(self):
        self.ensure_one()
        if not self.product_tmpl_id:
            self._sync_product()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product'),
            'res_model': 'product.template',
            'res_id': self.product_tmpl_id.id,
            'view_mode': 'form',
        }

    def action_view_stock(self):
        self.ensure_one()
        if not self.product_id:
            self._sync_product()
        return {
            'type': 'ir.actions.act_window',
            'name': _('On Hand - %s', self.display_name),
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('product_id', '=', self.product_id.id)],
            'context': {
                'default_product_id': self.product_id.id,
                'search_default_internal_loc': 1,
            },
        }
