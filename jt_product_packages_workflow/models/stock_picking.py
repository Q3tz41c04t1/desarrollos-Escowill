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

import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):

    _inherit = 'stock.picking'

    production_id = fields.Many2one(
        'mrp.production', string='Manufacturing Order')
    machine = fields.Char(related='production_id.maquina')
    total_packages = fields.Integer(string='Total Packages before backorder')
    comm_agent_id = fields.Many2one('res.users', string='Commercial Agent')
    is_delivery = fields.Boolean(string='Is Delivery Order')
    is_old_rec = fields.Boolean()
    sale_ref_id = fields.Many2one('sale.order', string='Sale Reference ID')
    mo_flag_id = fields.Many2one(
        'mrp.production', string='MRP Production Flag')
    flag_stock_delivery = fields.Boolean(string='From Stock Delivery')
    from_custom_barcode = fields.Boolean(
        string='Created from custom barcode app')

    active = fields.Boolean(string='Active/Archive', default=True)

    @api.multi
    def _check_entire_pack(self):
        """ This function check if entire packs are moved in the picking"""
        for picking in self:
            origin_packages = picking.move_line_ids.mapped("package_id")
            if self._context.get('packages'):
                origin_packages = self.env['stock.quant.package'].sudo().browse(self._context.get('packages'))
            for pack in origin_packages:
                if picking._check_move_lines_map_quant_package(pack):
                    package_level_ids = picking.package_level_ids.filtered(lambda pl: pl.package_id == pack)
                    move_lines_to_pack = picking.move_line_ids.filtered(lambda ml: ml.package_id == pack)
                    if not package_level_ids:
                        self.env['stock.package_level'].create({
                            'picking_id': picking.id,
                            'package_id': pack.id,
                            'location_id': pack.location_id.id,
                            'location_dest_id': picking.move_line_ids.filtered(lambda ml: ml.package_id == pack).mapped('location_dest_id')[:1].id,
                            'move_line_ids': [(6, 0, move_lines_to_pack.ids)]
                        })
                        move_lines_to_pack.write({
                            'result_package_id': pack.id,
                        })
                    else:
                        move_lines_in_package_level = move_lines_to_pack.filtered(lambda ml: ml.move_id.package_level_id)
                        move_lines_without_package_level = move_lines_to_pack - move_lines_in_package_level
                        for ml in move_lines_in_package_level:
                            ml.write({
                                'result_package_id': pack.id,
                                'package_level_id': ml.move_id.package_level_id.id,
                            })
                        move_lines_without_package_level.write({
                            'result_package_id': pack.id,
                            'package_level_id': package_level_ids[0].id,
                        })

    # Overriden method to prevent move done
    def action_done(self):
        todo_moves = self.mapped('move_lines').filtered(lambda self: self.state in [
            'draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
        # Check if there are ops not linked to moves yet
        for pick in self:
            for ops in pick.move_line_ids.filtered(lambda x: not x.move_id):
                # Search move with this product
                moves = pick.move_lines.filtered(
                    lambda x: x.product_id == ops.product_id)
                moves = sorted(moves, key=lambda m: m.quantity_done <
                               m.product_qty, reverse=True)
                if moves:
                    ops.move_id = moves[0].id
                else:
                    new_move = self.env['stock.move'].create({
                        'name': _('New Move:') + ops.product_id.display_name,
                        'product_id': ops.product_id.id,
                        'product_uom_qty': ops.qty_done,
                        'product_uom': ops.product_uom_id.id,
                        'location_id': pick.location_id.id,
                        'location_dest_id': pick.location_dest_id.id,
                        'picking_id': pick.id,
                        'picking_type_id': pick.picking_type_id.id,
                    })
                    ops.move_id = new_move.id
                    new_move._action_confirm()
                    todo_moves |= new_move
                    # 'qty_done': ops.qty_done})
        todo_moves._action_done()
        if not self._context.get('flag_validate_package') and not self._context.get('mo'):
            self.write({'date_done': fields.Datetime.now()})
        return True

    # To prevent  backorder creation wizard for packages validation purpose
    def action_generate_backorder_wizard(self):
        if self._context.get('flag_validate_package'):
            return self.action_done()
        else:
            return super(StockPicking, self).action_generate_backorder_wizard()

    def update_old_records(self):
        records = self.env['stock.picking'].search(
            [('is_old_rec', '=', False), ('active', '=', False)])
        for record in records:
            record.active = True
            record.is_old_rec = True

    @api.model
    def create(self, vals):
        if not vals.get('owner_id'):
            if vals.get('partner_id'):
                vals['owner_id'] = vals.get('partner_id')
        vals['is_old_rec'] = True
        vals['active'] = True
        picking = super(StockPicking, self).create(vals)

        picking.active = True
        location_dest = picking.location_dest_id

        # Set type code
        usage = False
        if location_dest:
            usage = location_dest.usage

        # Set sale order
        order = False
        if picking.sale_id:
            order = picking.sale_id
        elif picking.origin:
            sale = self.env['sale.order'].search(
                [('name', '=', picking.origin)], limit=1)
            if sale:
                order = sale

        if order and not picking.from_custom_barcode and picking.picking_type_code == 'outgoing' and usage == 'customer':
            warehouse_id = order.warehouse_id
            delivery_steps = warehouse_id.delivery_steps
            if delivery_steps == 'pick_pack_ship':
                picking.active = False

        if picking.from_custom_barcode or picking.flag_stock_delivery:
            picking.active = True

        if not picking.owner_id and order:
            picking.owner_id = order.partner_id.id

        return picking

    # Overridden method to pass context
    @api.one
    def action_assign_owner(self):
        self.move_line_ids.with_context(set_owner=True).write(
            {'owner_id': self.owner_id.id})

    # When automatic done qty fill and comes here to fill package sequence and
    # put line in pack
    def _put_in_pack(self):
        package = super(StockPicking, self)._put_in_pack()
        new_package_name = self._context.get("mo_id", "")
        new_package_name += str(self._context.get("pkg_name", "")).zfill(4)
        package.name = new_package_name
        return package

    # Overridden method to auto done pick order
    def button_validate(self):
        # self.ensure_one()
        ctx = self._context
        if ctx.get('from_barcode_screen'):
            ctxx = self._context.copy()
            if not self._context.get('comm_agent_id'):
                ctxx['pick_idd'] = self.id
                if self.comm_agent_id:
                    ctxx.update({'comm_agent_id': self.comm_agent_id.id})
                if self.sale_id:
                    ctxx.update({'sale_id': self.sale_id.id})
                if not ctxx.get('sale_id') and self.sale_ref_id:
                    ctxx.update({'sale_id': self.sale_ref_id.id})
                if self.production_id:
                    ctxx.update({'production_id': self.production_id.id})

            back_wiz_rec = self.env['stock.backorder.confirmation'].create({
                'pick_ids': [(6, 0, [self.id])]
            })
            back_wiz_rec.with_context(ctxx).process()
            return self.env.ref('stock_barcode.stock_barcode_action_main_menu').read()[0]
        else:
            ctxx = self._context.copy()
            if not self._context.get('comm_agent_id'):
                ctxx['pick_idd'] = self.id
                if self.comm_agent_id:
                    ctxx.update({'comm_agent_id': self.comm_agent_id.id})
                if self.sale_id:
                    ctxx.update({'sale_id': self.sale_id.id})
                if not ctxx.get('sale_id') and self.sale_ref_id:
                    ctxx.update({'sale_id': self.sale_ref_id.id})
                if self.production_id:
                    ctxx.update({'production_id': self.production_id.id})
                    return super(StockPicking, self).with_context(ctxx).button_validate()
                return super(StockPicking, self).button_validate()
            else:
                return super(StockPicking, self).button_validate()

    def get_barcode_view_state(self):
        """ Return the initial state of the barcode view as a dict.
        """
        pickings = self.read([
            'package_ids',
            'move_line_ids',
            'picking_type_id',
            'location_id',
            'location_dest_id',
            'name',
            'state',
            'picking_type_code',
        ])
        for picking in pickings:
            picking['package_ids'] = self.env['stock.quant.package'].browse(picking.pop('package_ids')).read([
                'id',
                'name',
                'display_name',
                'location_id',
                'owner_id',
                'packaging_id',
                'quant_ids',
                'shipping_weight',
                'weight',
            ])

            picking['move_line_ids'] = self.env['stock.move.line'].browse(picking.pop('move_line_ids')).read([
                'product_id',
                'location_id',
                'location_dest_id',
                'qty_done',
                'display_name',
                'product_uom_qty',
                'product_uom_id',
                'product_barcode',
                'owner_id',
                'lot_id',
                'lot_name',
                'package_id',
                'result_package_id',
                'dummy_id',
            ])
            for move_line_id in picking['move_line_ids']:
                move_line_id['product_id'] = self.env['product.product'].browse(move_line_id.pop('product_id')[0]).read([
                    'id',
                    'tracking',
                    'barcode',
                ])[0]
                move_line_id['location_id'] = self.env['stock.location'].browse(move_line_id.pop('location_id')[0]).read([
                    'id',
                    'display_name',
                ])[0]
                move_line_id['location_dest_id'] = self.env['stock.location'].browse(move_line_id.pop('location_dest_id')[0]).read([
                    'id',
                    'display_name',
                ])[0]
            picking['location_id'] = self.env['stock.location'].browse(
                picking.pop('location_id')[0]).read()[0]
            picking['location_dest_id'] = self.env['stock.location'].browse(
                picking.pop('location_dest_id')[0]).read()[0]
            picking['group_stock_multi_locations'] = self.env.user.has_group(
                'stock.group_stock_multi_locations')
            picking['group_tracking_owner'] = self.env.user.has_group(
                'stock.group_tracking_owner')
            picking['group_tracking_lot'] = self.env.user.has_group(
                'stock.group_tracking_lot')
            picking['group_production_lot'] = self.env.user.has_group(
                'stock.group_production_lot')
            picking['group_uom'] = self.env.user.has_group('uom.group_uom')
            picking['use_create_lots'] = self.env['stock.picking.type'].browse(
                picking['picking_type_id'][0]).use_create_lots
            picking['use_existing_lots'] = self.env['stock.picking.type'].browse(
                picking['picking_type_id'][0]).use_existing_lots
            picking['show_entire_packs'] = self.env['stock.picking.type'].browse(
                picking['picking_type_id'][0]).show_entire_packs
            picking['actionReportDeliverySlipId'] = self.env.ref(
                'stock.action_report_delivery').id
            if self.env.user.company_id.nomenclature_id:
                picking['nomenclature_id'] = [
                    self.env.user.company_id.nomenclature_id.id]
        return pickings

    @api.depends('move_type', 'move_lines.state', 'move_lines.picking_id')
    @api.one
    def _compute_state(self):
        if not self.move_lines:
            self.state = 'draft'
        elif any(move.state == 'draft' for move in self.move_lines):  # TDE FIXME: should be all ?
            self.state = 'draft'
        elif all(move.state == 'cancel' for move in self.move_lines):
            self.state = 'cancel'
        elif all(move.state in ['cancel', 'done'] for move in self.move_lines):
            self.state = 'done'
        else:
            relevant_move_state = self.move_lines._get_relevant_state_among_moves()
            if relevant_move_state == 'partially_available':
                self.state = 'assigned'
            else:
                if self.sale_id:
                    order = self.sale_id
                    if order.warehouse_id.delivery_steps == 'pick_pack_ship' and self.picking_type_code == 'outgoing':
                        self.state = 'waiting'
                    else:
                        self.state = relevant_move_state
                else:
                    self.state = relevant_move_state


# Overide count transfer orders for inventory dashboard to count only
# active transfer ADDED DOMAIN
class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def _compute_picking_count(self):
        # TDE TODO count picking can be done using previous two
        domains = {
            'count_picking_draft': [('state', '=', 'draft'), ('active', '=', True)],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting')), ('active', '=', True)],
            'count_picking_ready': [('state', '=', 'assigned'), ('active', '=', True)],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed')), ('active', '=', True)],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed')), ('active', '=', True)],
            'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting')), ('active', '=', True)],
        }
        for field in domains:
            new_domain = []
            new_domain.extend(domains[field])
            new_domain.append(('active', '=', True))
            data = self.env['stock.picking'].read_group(new_domain +
                                                        [('state', 'not in', ('done', 'cancel')),
                                                         ('picking_type_id', 'in', self.ids)],
                                                        ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            for record in self:
                record[field] = count.get(record.id, 0)
        for record in self:
            record.rate_picking_late = record.count_picking and record.count_picking_late * \
                100 / record.count_picking or 0
            record.rate_picking_backorders = record.count_picking and record.count_picking_backorders * \
                100 / record.count_picking or 0
