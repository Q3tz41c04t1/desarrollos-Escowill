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

from odoo import models, api, fields
from psycopg2 import OperationalError


class StockQuant(models.Model):

    _inherit = 'stock.quant'

    user_id = fields.Many2one('res.users', string='Commercial agent')
    production_id = fields.Many2one(
        'mrp.production', string='Production Order')
    sale_id = fields.Many2one('sale.order', string='Sale Order')

    def remove_empty_stock(self):
        quants = self.search([('reserved_quantity', '=', 0), ('quantity',
                                                              '=', 0), ('package_id', '!=', False)]).sudo().unlink()

    @api.model
    def create(self, vals):
        res = super(StockQuant, self).create(vals)
        if res.package_id:
            package = self.env['stock.quant.package'].browse(res.package_id.id)
            if package:
                sequence = self.env['package.sequence'].search([('package_name', '=', package.name)], limit=1)
                if sequence:
                    if sequence.sale_id:
                        res['sale_id'] = sequence.sale_id.id
                        if sequence.sale_id.user_id:
                            res['user_id'] = sequence.sale_id.user_id.id
                    if sequence.manufacturing_order_id:
                        res['production_id'] = sequence.manufacturing_order_id.id
        self.remove_empty_stock()
        if not res.owner_id:
            if self._context.get('line_owner_id'):
                res.owner_id = int(self._context.get('line_owner_id'))
        return res

    @api.multi
    def write(self, vals):
        self.ensure_one()
        res = super(StockQuant, self).write(vals)
        self.remove_empty_stock()
        return res

    @api.model
    def default_get(self, fields):
        res = super(StockQuant, self).default_get(fields)
        ctx = self._context
        if ctx.get('comm_agent_id'):
            res['user_id'] = ctx.get('comm_agent_id')
        if ctx.get('sale_id'):
            res['sale_id'] = ctx.get('sale_id')
        elif ctx.get('production_id'):
            mo = self.env['mrp.production'].browse(
                int(ctx.get('production_id')))
            if mo and mo.sale_id:
                res['sale_id'] = mo.sale_id.id
        if ctx.get('production_id'):
            res['production_id'] = ctx.get('production_id')
        if ctx.get('line_owner_id'):
            res['owner_id'] = int(self._context.get('line_owner_id'))
        return res

    @api.model
    def _update_available_quantity(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None, in_date=None):
        self = self.sudo()
        quants = False
        if quantity < 0:

            pick_idd = False
            if self._context.get('pick_idd'):
                pick_idd = self.env['stock.picking'].browse(int(self._context.get('pick_idd')))
            if pick_idd and '/PACK/' in pick_idd.name:
                quants = self._gather(product_id, location_id, lot_id=lot_id,
                                      package_id=package_id, owner_id=owner_id, strict=True)
            else:
                if self._context.get('is_inv_adj'):
                    quants = self._gather(product_id, location_id, lot_id=lot_id,
                                          package_id=package_id, owner_id=owner_id, strict=True)
                else:
                    quants = self._gather(
                        product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=False, strict=True)
            if pick_idd and pick_idd.from_custom_barcode:
                quants = self._gather(product_id, location_id, lot_id=lot_id,
                                      package_id=package_id, owner_id=owner_id, strict=True)
        else:
            quants = self._gather(product_id, location_id, lot_id=lot_id,
                                  package_id=package_id, owner_id=owner_id, strict=True)

        incoming_dates = [d for d in quants.mapped('in_date') if d]
        incoming_dates = [fields.Datetime.from_string(
            incoming_date) for incoming_date in incoming_dates]
        if in_date:
            incoming_dates += [in_date]
        # If multiple incoming dates are available for a given lot_id/package_id/owner_id, we
        # consider only the oldest one as being relevant.
        if incoming_dates:
            in_date = fields.Datetime.to_string(min(incoming_dates))
        else:
            in_date = fields.Datetime.now()

        for quant in quants:
            try:
                with self._cr.savepoint():
                    self._cr.execute("SELECT 1 FROM stock_quant WHERE id = %s FOR UPDATE NOWAIT", [
                                     quant.id], log_exceptions=False)
                    quant.write({
                        'quantity': quant.quantity + quantity,
                        'in_date': in_date,
                    })
                    break
            except OperationalError as e:
                if e.pgcode == '55P03':  # could not obtain the lock
                    continue
                else:
                    raise
        else:
            self.create({
                'product_id': product_id.id,
                'location_id': location_id.id,
                'quantity': quantity,
                'lot_id': lot_id and lot_id.id,
                'package_id': package_id and package_id.id,
                'owner_id': owner_id and owner_id.id,
                'in_date': in_date,
            })
        return self._get_available_quantity(product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id, strict=False, allow_negative=True), fields.Datetime.from_string(in_date)
