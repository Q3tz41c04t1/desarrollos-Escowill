# -*- coding: utf-8 -*-
##############################################################################
#
#    Jupical Technologies Pvt. Ltd.
#    Copyright (C) 2018-TODAY Jupical Technologies(<http://www.jupical.com>).
#    Author: Jupical Technologies Pvt. Ltd.(<http://www.jupical.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, api, fields, _
from odoo.tools import float_compare
from odoo.exceptions import ValidationError, UserError


class SaleOrder(models.Model):

    _inherit = 'sale.order'

    customer_po = fields.Char('Customer purchase order')
    more_info = fields.Char('More information')
    is_stock_product = fields.Boolean(string='Is Stock Product?')

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        for order in self:
            if order.is_stock_product:
                order.delivery_count = len(order.picking_ids)
            else:
                delivery_steps = order.warehouse_id.delivery_steps
                if delivery_steps == 'pick_pack_ship':
                    counter = 0
                    for picking in order.picking_ids:
                        type_code = picking.picking_type_code
                        if type_code != 'outgoing':
                            counter += 1
                    order.delivery_count = counter
                else:
                    order.delivery_count = len(order.picking_ids)

    @api.multi
    def action_view_delivery(self):
        self.ensure_one()
        '''
        This function returns an action that display existing delivery orders
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one delivery order to show.
        '''
        res = super(SaleOrder, self).action_view_delivery()

        domain = res.get('domain')
        if not self.is_stock_product:
            delivery_steps = self.warehouse_id.delivery_steps
            if delivery_steps == 'pick_pack_ship':
                domain.append(('picking_type_code', '!=', 'outgoing'))
                res.update({'domain': domain})
        return res


class SaleOrderLine(models.Model):

    _inherit = 'sale.order.line'

    total_packages = fields.Integer(
        string='Total Packages', compute='_compute_total_packages', store=True)
    customer_key = fields.Char('Customer key')
    newqty = fields.Float(string='Expected Package Qty')

    @api.multi
    def _compute_has_pending_done(self):
        for line in self:
            line.has_pending_done = False
            total_pkg = line.total_packages
            count_qty = 0
            delivered_pkg = 0
            for picking in line.order_id.picking_ids:  # .search([('state', '=', 'done')]):
                if picking.state == 'done':
                    for move_line in picking.move_line_ids:  # .search([('product_id', '=', line.product_id.id)]):
                        if move_line.product_id.id == line.product_id.id:
                            count_qty += move_line.qty_done
                            delivered_pkg += 1
            if count_qty >= line.product_uom_qty or delivered_pkg >= total_pkg:
                line.has_pending_done = True

    has_pending_done = fields.Boolean(
        string='Has Delivery Done', compute='_compute_has_pending_done')

    # Overriden method to check expected qty for selected package and give msg
    # if qty not not fulfil
    @api.model
    def create(self, vals):
        if vals.get('product_packaging'):
            product = self.env['product.product'].browse(
                vals.get('product_id'))
            default_uom = product.uom_id
            uom = self.env['uom.uom'].browse(vals.get('product_uom'))
            pack = self.env['product.packaging'].browse(
                vals.get('product_packaging'))
            qty = vals.get('product_uom_qty')
            q = default_uom._compute_quantity(pack.qty, uom)
            if qty and q and (qty % q):
                newqty = qty - (qty % q) + q
                vals['product_uom_qty'] = newqty
                raise ValidationError(_("This product (%s) is packaged by %.2f %s. You should sell %.2f %s.") % (
                    product.display_name, pack.qty, default_uom.name, newqty, uom.name))
        return super(SaleOrderLine, self).create(vals)

    # Overriden method to check expected qty for selected package and give msg
    # if qty not not fulfil
    @api.multi
    def write(self, vals):
        self.ensure_one()
        if vals.get('product_packaging') or vals.get('product_uom_qty'):
            product = self.product_id
            default_uom = product.uom_id
            uom = self.product_uom
            pack = False
            if 'product_packaging' in vals:
                pack = self.env['product.packaging'].browse(
                    vals.get('product_packaging'))
            elif self.product_packaging:
                pack = self.product_packaging
            if pack:
                qty = False
                if vals.get('product_uom_qty'):
                    qty = vals.get('product_uom_qty')
                else:
                    qty = self.product_uom_qty
                q = default_uom._compute_quantity(pack.qty, uom)
                if qty and q and (qty % q):
                    newqty = qty - (qty % q) + q
                    raise ValidationError(_("This product (%s) is packaged by %.2f %s. You should sell %.2f %s.") % (
                        product.display_name, pack.qty, default_uom.name, newqty, uom.name))
        return super(SaleOrderLine, self).write(vals)

    # Compute packages total
    @api.multi
    @api.depends('product_uom_qty', 'product_packaging')
    def _compute_total_packages(self):
        for line in self:
            line.total_packages = 0
            if line.product_packaging and line.product_uom_qty:
                if line.product_packaging.qty:
                    line.total_packages = line.product_uom_qty / line.product_packaging.qty

    # Code to auto fill expected qty for package
    @api.multi
    def _check_package(self):
        default_uom = self.product_id.uom_id
        pack = self.product_packaging
        qty = self.product_uom_qty
        q = default_uom._compute_quantity(pack.qty, self.product_uom)
        if qty and q and (qty % q):
            newqty = qty - (qty % q) + q
            self.product_uom_qty = newqty
            return {
                'warning': {
                    'title': _('Warning'),
                    'message': _("This product is packaged by %.2f %s. You should sell %.2f %s.") % (pack.qty, default_uom.name, newqty, self.product_uom.name),
                },
            }
        return {}

    # Method to prevent delivery creation if sale line is belongs to stock order
    @api.multi
    def _action_launch_stock_rule(self):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        errors = []
        for line in self:
            if line.state != 'sale' or not line.product_id.type in ('consu', 'product'):
                continue
            qty = line._get_qty_procurement()
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            group_id = line.order_id.procurement_group_id
            if not group_id:
                group_id = self.env['procurement.group'].create({
                    'name': line.order_id.name, 'move_type': line.order_id.picking_policy,
                    'sale_id': line.order_id.id,
                    'partner_id': line.order_id.partner_shipping_id.id,
                })
                line.order_id.procurement_group_id = group_id
            else:
                # In case the procurement group is already created and the order was
                # cancelled, we need to update certain values of the group.
                updated_vals = {}
                if group_id.partner_id != line.order_id.partner_shipping_id:
                    updated_vals.update(
                        {'partner_id': line.order_id.partner_shipping_id.id})
                if group_id.move_type != line.order_id.picking_policy:
                    updated_vals.update(
                        {'move_type': line.order_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.product_uom_qty - qty

            procurement_uom = line.product_uom
            quant_uom = line.product_id.uom_id
            get_param = self.env['ir.config_parameter'].sudo().get_param
            if procurement_uom.id != quant_uom.id and get_param('stock.propagate_uom') != '1':
                product_qty = line.product_uom._compute_quantity(
                    product_qty, quant_uom, rounding_method='HALF-UP')
                procurement_uom = quant_uom

            try:
                route_ids = line.product_id.route_ids
                flag = False
                for route in route_ids:
                    if route.name in ['Make To Order', 'Manufacture']:
                        flag = True
                if (not line.order_id.is_stock_product) or (line.order_id.is_stock_product and flag):
                    self.env['procurement.group'].run(line.product_id, product_qty, procurement_uom,
                                                      line.order_id.partner_shipping_id.property_stock_customer, line.name, line.order_id.name, values)
            except UserError as error:
                errors.append(error.name)
        if errors:
            raise UserError('\n'.join(errors))
        return True
