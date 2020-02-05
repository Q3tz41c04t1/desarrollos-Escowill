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

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TransferPackageWizard(models.TransientModel):

    _name = 'transfer.package.wizard'
    _description = 'Transfer Package Wizard'

    product_id = fields.Many2one('product.product', string='Producto')
    partner_id = fields.Many2one('res.partner', string='Pertenece al cliente')
    user_id = fields.Many2one('res.users', string='Agente comercial')
    production_id = fields.Many2one('mrp.production', string='MRP Production')
    sale_id = fields.Many2one('sale.order')
    location_id = fields.Many2one(
        'stock.location', string='Ubicacion Destino', domain="[('usage', '=', 'internal')]")

    tranfer_line_ids = fields.One2many(
        'transfer.pkg.line', 'tranfer_wizard_id', string='Transfer Location Lines')
    scanned_type = fields.Selection(
        [('product', 'Product'), ('package', 'package')], string='Scan Type')
    mode = fields.Selection([
        ('internal_transfer', 'Internal Transfer'),
        ('delivery_on_request', 'Delivery On Request'),
        ('stock_delivery', 'Stock Delivery')])
    packages_list = fields.Char(string='Location Wise Package Qty')
    packages_quant = fields.Char(string='Location Wise Package')
    total_packages = fields.Integer(string='Total de cajas')
    package_name = fields.Char(string='Package Name')
    warn_msg = fields.Text(string='Warning Message')

    # Fields for stock delivery process
    st_product_id = fields.Many2one('product.product', string='Product')

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    st_partner_id = fields.Many2one(
        'res.partner', string='Customer', related='sale_order_id.partner_id')

    # Set sales order display domain based on availability of pending package
    @api.multi
    @api.onchange('st_product_id')
    def _onchange_st_product_id(self):
        if not self.st_product_id:
            return {'domain': {'sale_order_id': [('state', '=', 'sale'), ('is_stock_product', '=', True)]}}
        else:
            orders = self.env['sale.order'].search(
                [('state', '=', 'sale'), ('is_stock_product', '=', True)])
            order_list = []
            for order in orders:
                for line in order.order_line:
                    if line.product_id.id == self.st_product_id.id and not line.has_pending_done:
                        if order.id not in order_list:
                            order_list.append(order.id)
            return {'domain': {'sale_order_id': [('state', '=', 'sale'), ('is_stock_product', '=', True), ('id', 'in', order_list)]}}

    # Set calculation of total packages, pending packages, delivered packages
    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):

        self.boxes_in_order = 0
        self.boxes_delivered = 0
        self.boxes_pending = 0

        if self.sale_order_id and self.st_product_id:
            product_flag = False
            for line in self.sale_order_id.order_line:
                if line.product_id.id == self.st_product_id.id:
                    product_flag = True

                if line.product_id.id == self.st_product_id.id:
                    self.boxes_in_order = line.total_packages
                    break
            if not product_flag:
                raise ValidationError("This order does not contain the product ({0}), please select other sales order".format(
                    self.st_product_id.display_name))

            total_packages = 0
            total_qty = 0
            for picking in self.sale_order_id.picking_ids:
                if picking.picking_type_code == 'outgoing' and picking.state == 'done':
                    for line in picking.move_line_ids:
                        if line.product_id.id == self.st_product_id.id:
                            total_qty += line.qty_done
                            if line.package_id or line.result_package_id:
                                total_packages += 1

            if total_packages == 0:
                pickings = self.env['stock.picking'].sudo().search(['|', ('sale_id', '=', self.sale_order_id.id), (
                    'sale_ref_id', '=', self.sale_order_id.id), ('state', '=', 'done')])
                for picking in pickings:
                    if picking.picking_type_code == 'outgoing':
                        for line in picking.move_line_ids:
                            if line.product_id.id == self.st_product_id.id:
                                total_qty += line.qty_done
                                if line.package_id or line.result_package_id:
                                    total_packages += 1

            self.boxes_delivered = total_packages
            self.boxes_pending = self.boxes_in_order - self.boxes_delivered

            if self.boxes_in_order > 0 and self.boxes_in_order == self.boxes_delivered or self.boxes_pending == 0:
                raise ValidationError(
                    "There are no any pending packages to transfer \n Please select other order")

    boxes_in_order = fields.Integer(string='Boxes in order')
    boxes_delivered = fields.Integer(string='Delivered Boxes')
    boxes_pending = fields.Integer(string='Pending Boxes')

    # Validation function for packages lines
    @api.constrains('tranfer_line_ids')
    def _check_fill_any_package(self):
        flag1 = False
        flag2 = False
        flag3 = False
        msg = ""

        for line in self.tranfer_line_ids:
            if line.allow_mover:
                flag1 = True
                if line.packages_to_move > line.total_packages:
                    flag2 = True
                    msg = "Packages to move should be not be greater than total packages!"
                if line.packages_to_move == 0 or not line.packages_to_move:
                    flag3 = True
                    msg = "Please select packages to transfer for allow mover line!"
        if not flag1:
            msg = "Please select at least one package to transfer!"
        if not flag1 or flag2 or flag3:
            raise ValidationError(msg)

    def prepare_location_package_dict(self, flag, mode):
        # Prepare blank dict for packages by location
        packages_dict = {}
        location_ids = self.env['stock.location'].search([])
        for location in location_ids:
            if mode in ['delivery_on_request', 'stock_delivery'] and location.usage == 'customer':
                continue
            else:
                if flag in ["list", "quant"]:
                    packages_dict.update({location.id: []})
                elif flag == "dict":
                    packages_dict.update({location.id: 0})
        return packages_dict

    @api.model
    def default_get(self, fields):
        res = super(TransferPackageWizard, self).default_get(fields)

        quant_obj = self.env['stock.quant']

        # Get context
        ctx = self._context
        barcode = ctx.get('barcode')
        package_id = ctx.get('package_id')
        product_id = ctx.get('product_id')
        package_name = ctx.get('package_name')
        mode = False

        # Set default values
        if ctx.get('mode'):
            mode = ctx.get('mode')
        res['mode'] = mode

        if package_name:
            res['package_name'] = package_name

        # Check package or product scanned
        product = False
        package = False

        # To fetch product and package record from scanned package
        if barcode and package_id:
            res['scanned_type'] = 'package'
            package = self.env['stock.quant.package'].browse(package_id)
            quantt = quant_obj.search(
                [('package_id', '=', package_id)], limit=1)
            if quantt:
                if quantt.production_id:
                    res.update({'production_id': quantt.production_id.id})
            if package:
                for quant in package.quant_ids:
                    if quant.product_id:
                        product = quant.product_id
                        break
        if barcode and product_id:
            res['scanned_type'] = 'product'

        packages_dict = self.prepare_location_package_dict(
            flag="dict", mode=mode)
        packages_list = self.prepare_location_package_dict(
            flag="list", mode=mode)
        quant_list = self.prepare_location_package_dict(
            flag="quant", mode=mode)

        # Remove blank total package location key-val
        def pop_blank_dict(dictt, flag):
            pop_lst = []
            for key, value in dictt.items():
                to_check = 0

                if flag == 'pkg_dict':
                    to_check = value
                elif flag == 'pkg_list':
                    to_check = len(value)
                elif flag == 'pkg_quant':
                    to_check = len(value)

                if to_check == 0:
                    pop_lst.append(key)

            for key in pop_lst:
                dictt.pop(key)

            return dictt

        def prepare_line_vals(dictt):
            # Fill transfer wizard lines
            line_vals = []
            for key, value in dictt.items():
                line_vals.append((0, 0, {
                    'location_id': int(key),
                    'total_packages': int(value),
                }))
            return line_vals

        def fill_package_by_location(lines, pkg_dict, pkg_list, pkg_quant):
            # Fill total packages by location
            for line in lines:
                if line.location_id:
                    # Updating total packages
                    pkg_dict.update(
                        {line.location_id.id: pkg_dict.get(line.location_id.id) + 1})

                    # Updating total qty per package by location
                    pkg_list.get(line.location_id.id).append(line.quantity)

                    # Updating total qty per package by location
                    pkg_quant.get(line.location_id.id).append(line.id)

            res.update({'total_packages': len(lines)})
            return {'pkg_dict': pkg_dict, 'pkg_list': pkg_list, 'pkg_quant': pkg_quant}

        error_flag = False
        flag_stock_del = False
        flag_del_req = False
        quant = False
        lines = False

        if product and package:
            domain = [('reserved_quantity', '=', 0),
                      ('quantity', '>', 0),
                      ('product_id', '=', product.id)]

            line_domain = [('reserved_quantity', '=', 0),
                           ('quantity', '>', 0),
                           ('product_id', '=', product.id)]

            if mode == 'internal_transfer' or mode == 'delivery_on_request' and product:

                if mode == 'delivery_on_request':
                    lst_name = [product.name, product.display_name]
                    if any("stock" in str(nm).lower() for nm in lst_name):
                        flag_del_req = True

                # Set default fields
                res.update({'product_id': product.id})
                domain.append(('production_id', '!=', False))
                domain.append(('package_id.name', '=', package_name))
                quant = quant_obj.search(domain, limit=1)

                if quant and quant.production_id:

                    s_id = False
                    if quant.sale_id:
                        s_id = quant.sale_id.id
                    elif quant.production_id.sale_id:
                        s_id = quant.production_id.sale_id.id
                    res.update({
                        'partner_id': quant.owner_id and quant.owner_id.id or False,
                        'user_id': quant.user_id and quant.user_id.id or False,
                        'sale_id': s_id,
                        'production_id': quant.production_id.id,
                    })

                    # Prepare domain and fetch lines
                    line_domain.append(
                        ('production_id', '!=', False))
                    if quant.user_id:
                        line_domain.append(('user_id', '=', quant.user_id.id))
                    if quant.owner_id:
                        line_domain.append(
                            ('owner_id', '=', quant.owner_id.id))
                    if mode == 'delivery_on_request':
                        line_domain.append(
                            ('location_id.usage', '!=', 'customer'))
                    if mode == 'internal_transfer':
                        line_domain.append(
                            ('location_id.usage', '!=', 'customer'))
                    lines = quant_obj.search(line_domain)

                    if mode == 'internal_transfer' and not lines:
                        line_d = [('reserved_quantity', '=', 0),
                                  ('package_id', '!=', False),
                                  ('quantity', '>', 0),
                                  ('product_id', '=', product.id),
                                  ('production_id', '!=', False),
                                  ('location_id.usage', '!=', 'customer')]
                        lines = quant_obj.search(line_d)
                else:
                    error_flag = True
            elif mode == 'stock_delivery':
                orders = self.env['sale.order'].search(
                    [('state', '=', 'sale'), ('is_stock_product', '=', True)])
                product_flag = False
                for order in orders:
                    for line in order.order_line:
                        if line.product_id.id == product.id:
                            product_flag = True
                            break
                if not product_flag:
                    error_flag = True
                    flag_stock_del = True

                # Set default fields
                res['st_product_id'] = product.id
                line_domain.append(('package_id', '!=', False))
                line_domain.append(('location_id.usage', '!=', 'customer'))
                lines = quant_obj.search(line_domain)
        else:
            error_flag = True

        if error_flag:
            res['scanned_type'] = 'product'
            res['warn_msg'] = 'Scanned barcode is not match with any package. \n\n Please scan correct package'

            if flag_del_req:
                res['warn_msg'] = 'You can only scan non- "Delivery of stock" products in delivery on request process. \n\n Please scan correct package'
            if flag_stock_del:
                res['warn_msg'] = 'Scanned product is not match with any stock sales order. \n\n Please scan correct package'
        else:
            if lines:
                # Fill total packages by location
                result_dicts = fill_package_by_location(
                    lines, packages_dict, packages_list, quant_list)

                # Set default fields
                res.update({
                    'tranfer_line_ids': prepare_line_vals(pop_blank_dict(result_dicts.get('pkg_dict'), "pkg_dict")),
                    'packages_list': str(pop_blank_dict(result_dicts.get('pkg_list'), "pkg_list")),
                    'packages_quant': str(pop_blank_dict(result_dicts.get('pkg_quant'), "pkg_quant")),
                })
            else:
                res.update({
                    'scanned_type': 'product',
                    'warn_msg': 'No any packages to move. \n\n Please scan correct package',
                })
        return res

    def transfer_packages(self):

        quant_obj = self.env['stock.quant']
        picking_obj = self.env['stock.picking']
        picking_type_obj = self.env['stock.picking.type'].sudo()
        move_obj = self.env['stock.move']
        location_obj = self.env['stock.location']

        # Unlink quants which has 0 onhand quantity and 0 reserved quantity
        qs = quant_obj.search(
            [('package_id', '!=', False), ('quantity', '=', 0), ('reserved_quantity', '=', 0)])
        for q in qs:
            q.sudo().unlink()

        vals = {}
        vals['from_custom_barcode'] = True
        group_id = False

        if self.mode in ['internal_transfer', 'delivery_on_request', 'stock_delivery']:
            warehouse = False

            if self.mode == 'stock_delivery':
                # Added validation for stock delivery
                pkg_total = 0
                selected_pkg = 0
                for p_line in self.tranfer_line_ids:
                    if p_line.allow_mover:
                        selected_pkg += 1
                        pkg_total += p_line.packages_to_move
                if selected_pkg == 0 or selected_pkg < 0 or not selected_pkg:
                    raise ValidationError(
                        "Please select packages to transfer.")
                if pkg_total > self.boxes_pending or pkg_total > self.boxes_in_order:
                    raise ValidationError(
                        "Packages to transfer should not be greater than pending packages")

                if self.st_partner_id:
                    vals['partner_id'] = self.st_partner_id.id
                    vals['owner_id'] = self.st_partner_id.id

            if self.mode in ['delivery_on_request', 'stock_delivery']:
                location = location_obj.search(
                    [('usage', '=', 'customer')], limit=1)
                if location:
                    self.location_id = location.id

            if self.mode != 'stock_delivery' and self.partner_id:
                vals['partner_id'] = self.partner_id.id
                vals['owner_id'] = self.partner_id.id

            if self.user_id:
                vals['comm_agent_id'] = self.user_id.id

            if self.production_id:
                vals['mo_flag_id'] = self.production_id.id
                vals['production_id'] = self.production_id.id

            sl = False
            if self.sale_id:
                sl = self.sale_id
            elif self.sale_order_id:
                sl = self.sale_order_id
            if sl:
                if self.mode == 'stock_delivery' and not vals.get('production_id'):
                    sequences = self.env['package.sequence'].search(
                        [('sale_id', '=', sl.id)])
                    for seq in sequences:
                        if seq.manufacturing_order_id and seq.sequence:
                            MO_ref = seq.manufacturing_order_id.name.replace(
                                '/', '')
                            complete_name = str(MO_ref).replace(
                                '-', '') + seq.sequence
                            if complete_name == self.package_name:
                                vals['production_id'] = seq.manufacturing_order_id.id

                if self.mode == 'stock_delivery':
                    vals['comm_agent_id'] = sl.user_id.id

                vals['sale_ref_id'] = sl.id
                vals['origin'] = sl.name
                warehouse = sl.warehouse_id

                group = self.env['procurement.group'].sudo().search(
                    ['|', ('sale_id', '=', sl.id), ('name', '=', sl.name)], limit=1)
                if group:
                    group_id = group.id
                    vals['group_id'] = group_id

                if warehouse:
                    if self.mode == 'internal_transfer':
                        if warehouse.int_type_id:
                            vals['picking_type_id'] = warehouse.int_type_id.id
                    if self.mode in ['delivery_on_request', 'stock_delivery']:
                        if warehouse.out_type_id:
                            vals['picking_type_id'] = warehouse.out_type_id.id

            if not vals.get('picking_type_id'):
                if self.production_id and self.production_id.sale_id and self.production_id.sale_id.warehouse_id:
                    if self.mode == 'internal_transfer':
                        if self.production_id.sale_id.warehouse_id.int_type_id:
                            vals[
                                'picking_type_id'] = self.production_id.sale_id.warehouse_id.int_type_id.id
                    if self.mode == 'delivery_on_request':
                        if self.production_id.sale_id.warehouse_id.out_type_id:
                            vals[
                                'picking_type_id'] = self.production_id.sale_id.warehouse_id.out_type_id.id
            if self.mode == 'stock_delivery' and not vals.get('picking_type_id'):
                operation_typee = picking_type_obj.search(
                    [('name', 'in', ['Delivery Orders', 'Órdenes de entrega']), ('code', '=', 'outgoing')], limit=1)
                if operation_typee:
                    vals['picking_type_id'] = operation_typee.id

            for line in self.tranfer_line_ids:
                if line.allow_mover:
                    vals['location_id'] = line.location_id.id
                    vals['location_dest_id'] = self.location_id.id

                    vals_copy = vals.copy()
                    if not vals_copy.get('from_custom_barcode'):
                        vals_copy['from_custom_barcode'] = True
                        vals_copy['active'] = True
                    if self.mode == 'stock_delivery':
                        vals_copy['flag_stock_delivery'] = True
                    picking = picking_obj.create(vals_copy)
                    picking.active = True
                    move_vals = {}

                    # prepare qty
                    qty_dict = eval(self.packages_list)
                    qty_list = qty_dict.get(line.location_id.id)
                    qty = 0

                    quant_dict = eval(self.packages_quant)
                    quant_list = quant_dict.get(line.location_id.id)

                    for pkg in range(0, line.packages_to_move):
                        try:
                            qty += qty_list[pkg]
                        except:
                            _logger.warn('Not much quantity per package found')

                    move_vals['name'] = picking.location_id.name + \
                        ' → ' + picking.location_dest_id.name
                    move_vals['picking_id'] = picking.id
                    move_vals['location_id'] = picking.location_id.id
                    move_vals['location_dest_id'] = picking.location_dest_id.id
                    move_vals['product_uom_qty'] = qty
                    if self.mode == 'stock_delivery':
                        move_vals['product_id'] = self.st_product_id.id
                        move_vals['product_uom'] = self.st_product_id.uom_id.id
                    else:
                        move_vals['product_id'] = self.product_id.id
                        move_vals['product_uom'] = self.product_id.uom_id.id
                    move_vals['total_pkg'] = line.packages_to_move
                    move_vals['quant_list'] = str(quant_list)
                    if self.mode == 'stock_delivery' or self.mode not in ['internal_transfer', 'delivery_on_request']:
                        if group_id:
                            move_vals['group_id'] = group_id
                        elif picking.group_id:
                            move_vals['group_id'] = picking.group_id.id

                    if warehouse:
                        move_vals['warehouse_id'] = warehouse.id

                    move = move_obj.create(move_vals)
                    picking.action_confirm()
                    picking.action_assign()
                    for m_line in move.move_line_ids:
                        m_line.qty_done = m_line.product_uom_qty
                    picking.button_validate()

                    counter = 0
                    for i in quant_list:
                        if counter < line.packages_to_move:
                            quantt = quant_obj.browse(i)
                            if quantt:
                                quantt.sudo().unlink()
                        counter += 1

                    qs = quant_obj.search(
                        [('package_id', '!=', False), ('quantity', '=', 0), ('reserved_quantity', '=', 0)])
                    for q in qs:
                        q.sudo().unlink()


class TransferPKGLines(models.TransientModel):

    _name = 'transfer.pkg.line'
    _description = 'Transfer Package Line'

    tranfer_wizard_id = fields.Many2one('transfer.package.wizard')
    location_id = fields.Many2one('stock.location', string='Location')
    total_packages = fields.Integer(string='Total de cajas')
    allow_mover = fields.Boolean(string='Allow Mover?')
    packages_to_move = fields.Integer(string='Cajas a mover')

    @api.onchange('allow_mover')
    def _onchange_allow_mover(self):
        if not self.allow_mover:
            self.packages_to_move = 0
