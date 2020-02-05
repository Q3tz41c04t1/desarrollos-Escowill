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

from itertools import groupby
from operator import itemgetter

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockInventory(models.Model):

    _inherit = 'stock.inventory'

    def action_validate(self):
        return super(StockInventory, self.with_context(is_inv_adj=True)).action_validate()


class StockMoveLine(models.Model):

    _inherit = 'stock.move.line'

    is_last_line = fields.Boolean(string='Is Last Line?')
    is_validated = fields.Boolean(string="Is Validated?")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            # If the move line is directly create on the picking view.
            # If this picking is already done we should generate an
            # associated done move.
            if 'picking_id' in vals and not vals.get('move_id'):
                picking = self.env['stock.picking'].browse(vals['picking_id'])
                if picking.state == 'done':
                    product = self.env['product.product'].browse(
                        vals['product_id'])
                    new_move = self.env['stock.move'].create({
                        'name': _('New Move:') + product.display_name,
                        'product_id': product.id,
                        'product_uom_qty': 'qty_done' in vals and vals['qty_done'] or 0,
                        'product_uom': vals['product_uom_id'],
                        'location_id': 'location_id' in vals and vals['location_id'] or picking.location_id.id,
                        'location_dest_id': 'location_dest_id' in vals and vals['location_dest_id'] or picking.location_dest_id.id,
                        'state': 'done',
                        'additional': True,
                        'picking_id': picking.id,
                    })
                    vals['move_id'] = new_move.id

        mls = super(models.Model, self).create(vals_list)
        for ml in mls:
            if ml.state == 'done':
                if 'qty_done' in vals:
                    ml.move_id.product_uom_qty = ml.move_id.quantity_done
                if ml.product_id.type == 'product':
                    Quant = self.env['stock.quant']
                    quantity = ml.product_uom_id._compute_quantity(
                        ml.qty_done, ml.move_id.product_id.uom_id, rounding_method='HALF-UP')
                    in_date = None
                    available_qty, in_date = Quant._update_available_quantity(
                        ml.product_id, ml.location_id, -quantity, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
                    if available_qty < 0 and ml.lot_id:
                        # see if we can compensate the negative quants with
                        # some untracked quants
                        untracked_qty = Quant._get_available_quantity(
                            ml.product_id, ml.location_id, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                        if untracked_qty:
                            taken_from_untracked_qty = min(
                                untracked_qty, abs(quantity))
                            Quant._update_available_quantity(
                                ml.product_id, ml.location_id, -taken_from_untracked_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id)
                            Quant._update_available_quantity(
                                ml.product_id, ml.location_id, taken_from_untracked_qty, lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id)
                    Quant._update_available_quantity(ml.product_id, ml.location_dest_id, quantity, lot_id=ml.lot_id,
                                                     package_id=ml.result_package_id, owner_id=ml.owner_id, in_date=in_date)
                next_moves = ml.move_id.move_dest_ids.filtered(
                    lambda move: move.state not in ('done', 'cancel'))
                if 'packages' in self._context or 'flag_validate_pack' in self._context:
                    if len(next_moves) > 0:
                        next_moves._do_unreserve()
                        next_moves._action_assign()
                else:
                    next_moves._do_unreserve()
                    next_moves._action_assign()
        return mls

    def write(self, vals):
        """ Through the interface, we allow users to change the charateristics of a move line. If a
        quantity has been reserved for this move line, we impact the reservation directly to free
        the old quants and allocate the new ones.
        """
        if self.env.context.get('bypass_reservation_update'):
            return super(StockMoveLine, self).write(vals)

        Quant = self.env['stock.quant']
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        # We forbid to change the reserved quantity in the interace, but it is needed in the
        # case of stock.move's split.
        # TODO Move me in the update
        if 'product_uom_qty' in vals:
            for ml in self.filtered(lambda m: m.state in ('partially_available', 'assigned') and m.product_id.type == 'product'):
                if not ml.location_id.should_bypass_reservation():
                    qty_to_decrease = ml.product_qty - ml.product_uom_id._compute_quantity(
                        vals['product_uom_qty'], ml.product_id.uom_id, rounding_method='HALF-UP')
                    try:
                        Quant._update_reserved_quantity(ml.product_id, ml.location_id, -qty_to_decrease,
                                                        lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                    except UserError:
                        if ml.lot_id:
                            Quant._update_reserved_quantity(
                                ml.product_id, ml.location_id, -qty_to_decrease, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                        else:
                            raise

        triggers = [
            ('location_id', 'stock.location'),
            ('location_dest_id', 'stock.location'),
            ('lot_id', 'stock.production.lot'),
            ('package_id', 'stock.quant.package'),
            ('result_package_id', 'stock.quant.package'),
            ('owner_id', 'res.partner')
        ]
        updates = {}
        for key, model in triggers:
            if key in vals:
                updates[key] = self.env[model].browse(vals[key])

        if updates:
            for ml in self.filtered(lambda ml: ml.state in ['partially_available', 'assigned'] and ml.product_id.type == 'product'):
                if not ml.location_id.should_bypass_reservation():
                    try:
                        Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty,
                                                        lot_id=ml.lot_id, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                    except UserError:
                        if ml.lot_id:
                            Quant._update_reserved_quantity(
                                ml.product_id, ml.location_id, -ml.product_qty, lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
                        else:
                            raise

                if not updates.get('location_id', ml.location_id).should_bypass_reservation():
                    new_product_qty = 0
                    try:
                        q = Quant._update_reserved_quantity(ml.product_id, updates.get('location_id', ml.location_id), ml.product_qty, lot_id=updates.get('lot_id', ml.lot_id),
                                                            package_id=updates.get('package_id', ml.package_id), owner_id=updates.get('owner_id', ml.owner_id), strict=True)
                        new_product_qty = sum([x[1] for x in q])
                    except UserError:
                        if updates.get('lot_id'):
                            # If we were not able to reserve on tracked quants,
                            # we can use untracked ones.
                            try:
                                q = Quant._update_reserved_quantity(ml.product_id, updates.get('location_id', ml.location_id), ml.product_qty, lot_id=False,
                                                                    package_id=updates.get('package_id', ml.package_id), owner_id=updates.get('owner_id', ml.owner_id), strict=True)
                                new_product_qty = sum([x[1] for x in q])
                            except UserError:
                                pass
                    if new_product_qty != ml.product_qty:
                        new_product_uom_qty = ml.product_id.uom_id._compute_quantity(
                            new_product_qty, ml.product_uom_id, rounding_method='HALF-UP')
                        ml.with_context(
                            bypass_reservation_update=True).product_uom_qty = new_product_uom_qty

        # When editing a done move line, the reserved availability of a
        # potential chained move is impacted. Take care of running again
        # `_action_assign` on the concerned moves.
        next_moves = self.env['stock.move']
        if updates or 'qty_done' in vals:
            mls = self.filtered(lambda ml: ml.move_id.state ==
                                'done' and ml.product_id.type == 'product')
            if not updates:  # we can skip those where qty_done is already good up to UoM rounding
                mls = mls.filtered(lambda ml: not float_is_zero(
                    ml.qty_done - vals['qty_done'], precision_rounding=ml.product_uom_id.rounding))
            for ml in mls:
                # undo the original move line
                qty_done_orig = ml.move_id.product_uom._compute_quantity(
                    ml.qty_done, ml.move_id.product_id.uom_id, rounding_method='HALF-UP')
                in_date = Quant._update_available_quantity(ml.product_id, ml.location_dest_id, -qty_done_orig, lot_id=ml.lot_id,
                                                           package_id=ml.result_package_id, owner_id=ml.owner_id)[1]
                Quant._update_available_quantity(ml.product_id, ml.location_id, qty_done_orig, lot_id=ml.lot_id,
                                                 package_id=ml.package_id, owner_id=ml.owner_id, in_date=in_date)

                # move what's been actually done
                product_id = ml.product_id
                location_id = updates.get('location_id', ml.location_id)
                location_dest_id = updates.get(
                    'location_dest_id', ml.location_dest_id)
                qty_done = vals.get('qty_done', ml.qty_done)
                lot_id = updates.get('lot_id', ml.lot_id)
                package_id = updates.get('package_id', ml.package_id)
                result_package_id = updates.get(
                    'result_package_id', ml.result_package_id)
                owner_id = updates.get('owner_id', ml.owner_id)
                quantity = ml.move_id.product_uom._compute_quantity(
                    qty_done, ml.move_id.product_id.uom_id, rounding_method='HALF-UP')
                if not location_id.should_bypass_reservation():
                    ml._free_reservation(product_id, location_id, quantity,
                                         lot_id=lot_id, package_id=package_id, owner_id=owner_id)
                if not float_is_zero(quantity, precision_digits=precision):
                    available_qty, in_date = Quant._update_available_quantity(
                        product_id, location_id, -quantity, lot_id=lot_id, package_id=package_id, owner_id=owner_id)
                    if available_qty < 0 and lot_id:
                        # see if we can compensate the negative quants with
                        # some untracked quants
                        untracked_qty = Quant._get_available_quantity(
                            product_id, location_id, lot_id=False, package_id=package_id, owner_id=owner_id, strict=True)
                        if untracked_qty:
                            taken_from_untracked_qty = min(
                                untracked_qty, abs(available_qty))
                            Quant._update_available_quantity(
                                product_id, location_id, -taken_from_untracked_qty, lot_id=False, package_id=package_id, owner_id=owner_id)
                            Quant._update_available_quantity(
                                product_id, location_id, taken_from_untracked_qty, lot_id=lot_id, package_id=package_id, owner_id=owner_id)
                            if not location_id.should_bypass_reservation():
                                ml._free_reservation(
                                    ml.product_id, location_id, untracked_qty, lot_id=False, package_id=package_id, owner_id=owner_id)
                    Quant._update_available_quantity(
                        product_id, location_dest_id, quantity, lot_id=lot_id, package_id=result_package_id, owner_id=owner_id, in_date=in_date)

                # Unreserve and reserve following move in order to have the
                # real reserved quantity on move_line.
                next_moves |= ml.move_id.move_dest_ids.filtered(
                    lambda move: move.state not in ('done', 'cancel'))

                # Log a note
                if ml.picking_id:
                    ml._log_message(ml.picking_id, ml,
                                    'stock.track_move_template', vals)

        res = super(models.Model, self).write(vals)

        # Update scrap object linked to move_lines to the new quantity.
        if 'qty_done' in vals:
            for move in self.mapped('move_id'):
                if move.scrapped:
                    move.scrap_ids.write({'scrap_qty': move.quantity_done})

        # As stock_account values according to a move's `product_uom_qty`, we consider that any
        # done stock move should have its `quantity_done` equals to its `product_uom_qty`, and
        # this is what move's `action_done` will do. So, we replicate the
        # behavior here.
        if updates or 'qty_done' in vals:
            moves = self.filtered(
                lambda ml: ml.move_id.state == 'done').mapped('move_id')
            for move in moves:
                move.product_uom_qty = move.quantity_done
        if 'packages' in self._context or 'flag_validate_pack' in self._context:
            if len(next_moves.ids) > 0:
                next_moves._do_unreserve()
                next_moves._action_assign()
        else:
            next_moves._do_unreserve()
            next_moves._action_assign()
        return res


class StockMove(models.Model):

    _inherit = 'stock.move'

    total_pkg = fields.Integer(string='Total Packages to create')
    quant_list = fields.Char(string='Quant List')
    done_line_list = fields.Text(string='Done Line List', default="[]")

    # Overriden method to set mrp production reference in picking, for machine
    # name print purpose
    def _update_reserved_quantity(self, need, available_quantity, location_id, lot_id=None, package_id=None, owner_id=None, strict=True):
        """ Create or update move lines.
        """
        self.ensure_one()
        if not lot_id:
            lot_id = self.env['stock.production.lot']
        if not package_id:
            package_id = self.env['stock.quant.package']
        if not owner_id:
            owner_id = self.env['res.partner']
        taken_quantity = min(available_quantity, need)
        if not strict:
            taken_quantity_move_uom = self.product_id.uom_id._compute_quantity(
                taken_quantity, self.product_uom, rounding_method='DOWN')
            taken_quantity = self.product_uom._compute_quantity(
                taken_quantity_move_uom, self.product_id.uom_id, rounding_method='HALF-UP')

        quants = []

        if self.product_id.tracking == 'serial':
            rounding = self.env['decimal.precision'].precision_get(
                'Product Unit of Measure')
            if float_compare(taken_quantity, int(taken_quantity), precision_digits=rounding) != 0:
                taken_quantity = 0

        try:
            if not float_is_zero(taken_quantity, precision_rounding=self.product_id.uom_id.rounding):
                if self.picking_id and self.picking_id.from_custom_barcode and self.quant_list:
                    try:
                        # list(reversed(eval(self.quant_list)))
                        quant_list = eval(self.quant_list)
                        if self.total_pkg <= len(quant_list):
                            packages = quant_list[0:self.total_pkg]
                            for pkg_id in packages:
                                package = self.env[
                                    'stock.quant'].browse(pkg_id)
                                quants.extend(self.env['stock.quant']._update_reserved_quantity(
                                    self.product_id, location_id, self.product_uom_qty / self.total_pkg, lot_id=lot_id,
                                    package_id=package.package_id, owner_id=owner_id, strict=strict
                                ))
                        else:
                            quants = self.env['stock.quant']._update_reserved_quantity(
                                self.product_id, location_id, taken_quantity, lot_id=lot_id,
                                package_id=package_id, owner_id=owner_id, strict=strict
                            )
                    except:
                        quants = self.env['stock.quant']._update_reserved_quantity(
                            self.product_id, location_id, taken_quantity, lot_id=lot_id,
                            package_id=package_id, owner_id=owner_id, strict=strict
                        )
                else:
                    quants = self.env['stock.quant']._update_reserved_quantity(
                        self.product_id, location_id, taken_quantity, lot_id=lot_id,
                        package_id=package_id, owner_id=owner_id, strict=strict
                    )
        except UserError:
            taken_quantity = 0

        # Find a candidate move line to update or create a new one.
        for reserved_quant, quantity in quants:
            to_update = self.move_line_ids.filtered(lambda m: m.product_id.tracking != 'serial' and
                                                    m.location_id.id == reserved_quant.location_id.id and m.lot_id.id == reserved_quant.lot_id.id and m.package_id.id == reserved_quant.package_id.id and m.owner_id.id == reserved_quant.owner_id.id)
            if to_update:
                to_update[0].with_context(bypass_reservation_update=True).product_uom_qty += self.product_id.uom_id._compute_quantity(
                    quantity, to_update[0].product_uom_id, rounding_method='HALF-UP')
            else:
                if self.product_id.tracking == 'serial':
                    vals = self._prepare_move_line_vals(
                        quantity=1, reserved_quant=reserved_quant)
                    if self._context.get('mo') and vals.get('picking_id'):
                        picking = self.env['stock.picking'].browse(
                            vals.get('picking_id'))
                        picking.production_id = self._context.get('mo')
                        picking.comm_agent_id = self._context.get(
                            'comm_agent_id')
                    for i in range(0, int(quantity)):
                        self.env['stock.move.line'].create(vals)
                else:
                    vals = self._prepare_move_line_vals(
                        quantity=quantity, reserved_quant=reserved_quant)
                    if self._context.get('mo') and vals.get('picking_id'):
                        picking = self.env['stock.picking'].browse(
                            vals.get('picking_id'))
                        picking.production_id = self._context.get('mo')
                        picking.comm_agent_id = self._context.get(
                            'comm_agent_id')
                    self.env['stock.move.line'].create(vals)
        return taken_quantity

    ''' Main method calls when MARK AS DONE clicked in mrp
        - create automatic packages for picking and set done qty.
        - Set done pickingZone after packages generates.
    '''

    def _action_done(self):
        if self._context.get('final_step'):
            result = super(StockMove, self)._action_done()
            final_step = self._context.get('final_step')
            if final_step:
                for rec in self:
                    for move_line in rec.move_dest_ids:
                        mrp_order = self._context.get('production')
                        if mrp_order and not mrp_order.picking_id:
                            mrp_order.picking_id = move_line.picking_id and move_line.picking_id.id or False
            return result
        else:
            self.filtered(lambda move: move.state == 'draft')._action_confirm()
            moves = self.exists().filtered(lambda x: x.state not in ('done', 'cancel'))
            moves_todo = self.env['stock.move']
            for move in moves:
                if move.quantity_done <= 0:
                    if float_compare(move.product_uom_qty, 0.0, precision_rounding=move.product_uom.rounding) == 0:
                        move._action_cancel()

            # Create extra moves where necessary
            for move in moves:
                if move.state == 'cancel' or move.quantity_done <= 0:
                    continue

                moves_todo |= move._create_extra_move()

            # Split moves where necessary and move quants
            for move in moves_todo:
                rounding = self.env['decimal.precision'].precision_get(
                    'Product Unit of Measure')
                if not self._context.get('flag_validate_package'):
                    if float_compare(move.quantity_done, move.product_uom_qty, precision_digits=rounding) < 0:
                        # Need to do some kind of conversion here
                        qty_split = move.product_uom._compute_quantity(
                            move.product_uom_qty - move.quantity_done, move.product_id.uom_id, rounding_method='HALF-UP')
                        new_move = move._split(qty_split)
                        for move_line in move.move_line_ids:
                            if move_line.product_qty and move_line.qty_done:
                                try:
                                    move_line.write(
                                        {'product_uom_qty': move_line.qty_done})
                                except UserError:
                                    pass
                        move._unreserve_initial_demand(new_move)
            slot_line_ids = []
            if not self._context.get('flag_validate_package'):
                # moves_todo.mapped('move_line_ids')._action_done()
                move_line_ids = moves_todo.mapped('move_line_ids')
                todo_move_line_ids = []
                for line in move_line_ids:
                    if not line.is_validated:
                        todo_move_line_ids.append(line.id)
                slot_line_ids = todo_move_line_ids
                todo_move_line_ids = self.env[
                    'stock.move.line'].sudo().browse(todo_move_line_ids)
                todo_move_line_ids._action_done()
            else:
                move_line_ids = moves_todo.mapped('move_line_ids')
                todo_move_line_ids = []
                for line in move_line_ids:
                    if line.is_validated:
                        continue
                    line_id = self.env['stock.move.line'].browse(
                        int(self._context.get('line_id')))
                    flag_last_line = False
                    if line_id and line_id.package_id or line_id.result_package_id:
                        flag_last_line = True
                    if line.id != int(self._context.get('line_id')) or flag_last_line:
                        line.is_validated = True
                        todo_move_line_ids.append(line.id)
                slot_line_ids = todo_move_line_ids
                todo_move_line_ids = self.env[
                    'stock.move.line'].sudo().browse(todo_move_line_ids)
                todo_move_line_ids._action_done()
            if moves_todo:
                lst = eval(moves_todo.done_line_list)
                lst.append(slot_line_ids)
                moves_todo.done_line_list = str(lst)
            for result_package in moves_todo\
                    .mapped('move_line_ids.result_package_id')\
                    .filtered(lambda p: p.quant_ids and len(p.quant_ids) > 1):
                if len(result_package.quant_ids.filtered(lambda q: not float_is_zero(abs(q.quantity) + abs(q.reserved_quantity), precision_rounding=q.product_uom_id.rounding)).mapped('location_id')) > 1:
                    raise UserError(
                        _('You cannot move the same package content more than once in the same transfer or split the same package into two location.'))
            picking = moves_todo.mapped('picking_id')
            if not self._context.get('flag_validate_package'):
                moves_todo.write(
                    {'state': 'done', 'date': fields.Datetime.now()})
                moves_todo.mapped('move_dest_ids')._action_assign()
            # We don't want to create back order for scrap moves
            # Replace by a kwarg in master
            if self.env.context.get('is_scrap'):
                return moves_todo

            if not self._context.get('flag_validate_package'):
                if picking:
                    picking._create_backorder()
            return moves_todo

    def _action_assign(self):
        """ Reserve stock moves by creating their stock move lines. A stock move is
        considered reserved once the sum of `product_qty` for all its move lines is
        equal to its `product_qty`. If it is less, the stock move is considered
        partially available.
        """
        if self:
            packages = []
            assigned_moves = self.env['stock.move']
            partially_available_moves = self.env['stock.move']
            for move in self.filtered(lambda m: m.state in ['confirmed', 'waiting', 'partially_available']):
                missing_reserved_uom_quantity = move.product_uom_qty - move.reserved_availability
                missing_reserved_quantity = move.product_uom._compute_quantity(
                    missing_reserved_uom_quantity, move.product_id.uom_id, rounding_method='HALF-UP')
                if move.location_id.should_bypass_reservation()\
                        or move.product_id.type == 'consu':
                    # create the move line(s) but do not impact quants
                    if move.product_id.tracking == 'serial' and (move.picking_type_id.use_create_lots or move.picking_type_id.use_existing_lots):
                        for i in range(0, int(missing_reserved_quantity)):
                            self.env['stock.move.line'].create(
                                move._prepare_move_line_vals(quantity=1))
                    else:
                        to_update = move.move_line_ids.filtered(lambda ml: ml.product_uom_id == move.product_uom and
                                                                ml.location_id == move.location_id and
                                                                ml.location_dest_id == move.location_dest_id and
                                                                ml.picking_id == move.picking_id and
                                                                not ml.lot_id and
                                                                not ml.package_id and
                                                                not ml.owner_id)
                        if to_update:
                            to_update[
                                0].product_uom_qty += missing_reserved_uom_quantity
                        else:
                            if move.picking_id and move.picking_id.from_custom_barcode and move.quant_list:
                                # list(reversed(eval(self.quant_list)))
                                quant_list = eval(move.quant_list)
                                if move.total_pkg <= len(quant_list):
                                    packages = quant_list[0:move.total_pkg]
                                    for pkg_id in packages:
                                        package = self.env[
                                            'stock.quant'].browse(pkg_id)
                                        valss = move._prepare_move_line_vals(
                                            quantity=move.product_uom_qty / move.total_pkg, reserved_quant=package)
                                        self.env['stock.move.line'].create(valss)
                            else:
                                self.env['stock.move.line'].create(
                                    move._prepare_move_line_vals(quantity=missing_reserved_quantity))
                    assigned_moves |= move
                else:
                    if not move.move_orig_ids:
                        if move.procure_method == 'make_to_order':
                            continue
                        # If we don't need any quantity, consider the move
                        # assigned.
                        need = missing_reserved_quantity
                        if float_is_zero(need, precision_rounding=move.product_id.uom_id.rounding):
                            assigned_moves |= move
                            continue
                        # Reserve new quants and create move lines accordingly.
                        forced_package_id = move.package_level_id.package_id or None
                        available_quantity = self.env['stock.quant']._get_available_quantity(
                            move.product_id, move.location_id, package_id=forced_package_id)
                        if available_quantity <= 0:
                            continue
                        taken_quantity = move._update_reserved_quantity(
                            need, available_quantity, move.location_id, package_id=forced_package_id, strict=False)
                        if float_is_zero(taken_quantity, precision_rounding=move.product_id.uom_id.rounding):
                            continue
                        if need == taken_quantity:
                            assigned_moves |= move
                        else:
                            partially_available_moves |= move
                    else:
                        # Check what our parents brought and what our siblings took in order to
                        # determine what we can distribute.
                        # `qty_done` is in `ml.product_uom_id` and, as we will later increase
                        # the reserved quantity on the quants, convert it here in
                        # `product_id.uom_id` (the UOM of the quants is the UOM of the product).
                        move_lines_in = move.move_orig_ids.filtered(
                            lambda m: m.state == 'done').mapped('move_line_ids')
                        if self._context.get('flag_validate_pack') or self._context.get('mo'):
                            lst = eval(move.move_orig_ids[0].done_line_list)
                            if len(lst) > 0:
                                move_lines_in = self.env[
                                    'stock.move.line'].browse(lst[0])
                        keys_in_groupby = ['location_dest_id',
                                           'lot_id', 'result_package_id', 'owner_id']

                        def _keys_in_sorted(ml):
                            return (ml.location_dest_id.id, ml.lot_id.id, ml.result_package_id.id, ml.owner_id.id)

                        grouped_move_lines_in = {}
                        for k, g in groupby(sorted(move_lines_in, key=_keys_in_sorted), key=itemgetter(*keys_in_groupby)):
                            qty_done = 0
                            for ml in g:
                                qty_done += ml.product_uom_id._compute_quantity(
                                    ml.qty_done, ml.product_id.uom_id)
                            grouped_move_lines_in[k] = qty_done
                        move_lines_out_done = (move.move_orig_ids.mapped('move_dest_ids') - move)\
                            .filtered(lambda m: m.state in ['done'])\
                            .mapped('move_line_ids')
                        # As we defer the write on the stock.move's state at the end of the loop, there
                        # could be moves to consider in what our siblings already
                        # took.
                        moves_out_siblings = move.move_orig_ids.mapped(
                            'move_dest_ids') - move
                        moves_out_siblings_to_consider = moves_out_siblings & (
                            assigned_moves + partially_available_moves)
                        reserved_moves_out_siblings = moves_out_siblings.filtered(
                            lambda m: m.state in ['partially_available', 'assigned'])
                        move_lines_out_reserved = (
                            reserved_moves_out_siblings | moves_out_siblings_to_consider).mapped('move_line_ids')
                        keys_out_groupby = ['location_id',
                                            'lot_id', 'package_id', 'owner_id']

                        def _keys_out_sorted(ml):
                            return (ml.location_id.id, ml.lot_id.id, ml.package_id.id, ml.owner_id.id)

                        grouped_move_lines_out = {}
                        for k, g in groupby(sorted(move_lines_out_done, key=_keys_out_sorted), key=itemgetter(*keys_out_groupby)):
                            qty_done = 0
                            for ml in g:
                                qty_done += ml.product_uom_id._compute_quantity(
                                    ml.qty_done, ml.product_id.uom_id)
                            grouped_move_lines_out[k] = qty_done
                        for k, g in groupby(sorted(move_lines_out_reserved, key=_keys_out_sorted), key=itemgetter(*keys_out_groupby)):
                            grouped_move_lines_out[k] = sum(
                                self.env['stock.move.line'].concat(*list(g)).mapped('product_qty'))
                        available_move_lines = {key: grouped_move_lines_in[
                            key] - grouped_move_lines_out.get(key, 0) for key in grouped_move_lines_in.keys()}
                        # pop key if the quantity available amount to 0
                        available_move_lines = dict(
                            (k, v) for k, v in available_move_lines.items() if v)

                        if not available_move_lines:
                            continue
                        if self._context.get('flag_validate_pack') or self._context.get('mo'):
                            pass
                        else:
                            for move_line in move.move_line_ids.filtered(lambda m: m.product_qty):
                                if available_move_lines.get((move_line.location_id, move_line.lot_id, move_line.result_package_id, move_line.owner_id)):
                                    available_move_lines[
                                        (move_line.location_id, move_line.lot_id, move_line.result_package_id, move_line.owner_id)] -= move_line.product_qty
                        for (location_id, lot_id, package_id, owner_id), quantity in available_move_lines.items():
                            if self._context.get('flag_validate_pack') or self._context.get('mo'):
                                if package_id:
                                    packages.append(package_id.id)
                            need = move.product_qty - \
                                sum(move.move_line_ids.mapped('product_qty'))
                            # `quantity` is what is brought by chained done move lines. We double check
                            # here this quantity is available on the quants themselves. If not, this
                            # could be the result of an inventory adjustment that removed totally of
                            # partially `quantity`. When this happens, we chose to reserve the maximum
                            # still available. This situation could not happen on MTS move, because in
                            # this case `quantity` is directly the quantity on the
                            # quants themselves.
                            available_quantity = self.env['stock.quant']._get_available_quantity(
                                move.product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=True)
                            if float_is_zero(available_quantity, precision_rounding=move.product_id.uom_id.rounding):
                                continue
                            taken_quantity = 0
                            if move.picking_id and not move.picking_id.active and move.picking_id.picking_type_code == 'outgoing' and move.picking_id.sale_id and move.picking_id.picking_type_id.warehouse_id and move.picking_id.picking_type_id.warehouse_id.delivery_steps == 'pick_pack_ship':
                                taken_quantity = 0
                            else:
                                taken_quantity = move._update_reserved_quantity(need, min(
                                    quantity, available_quantity), location_id, lot_id, package_id, owner_id)
                            if float_is_zero(taken_quantity, precision_rounding=move.product_id.uom_id.rounding):
                                continue
                            if need - taken_quantity == 0.0:
                                assigned_moves |= move
                                break
                            partially_available_moves |= move

            partially_available_moves.write({'state': 'partially_available'})
            assigned_moves.write({'state': 'assigned'})

            if self._context.get('flag_validate_pack') or self._context.get('mo'):
                self.mapped('picking_id').with_context(
                    packages=packages)._check_entire_pack()
            else:
                self.mapped('picking_id')._check_entire_pack()
