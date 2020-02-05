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


class BarcodeDeliverProducts(models.TransientModel):

    _name = 'barcode.deliver.products.wizard'
    _description = 'Model to calculate deliver product packages'

    picking_id = fields.Many2one('stock.picking', string='Picking Order')
    message = fields.Text(string='Warning Message')
    total_packages = fields.Integer(string='Total Packages')
    packages_to_validate = fields.Integer('Packages to validate')

    @api.model
    def default_get(self, fields):
        res = super(BarcodeDeliverProducts, self).default_get(fields)

        ctx = self._context
        if ctx.get('default_picking_id'):

            picking = self.env['stock.picking'].browse(
                ctx.get('default_picking_id'))
            total_packages = len(picking.move_line_ids.ids)

            message = "Esta producción esta conformada por un total de "
            if picking.backorder_id:
                backorder = picking.backorder_id
                total_bk_pkg = backorder.total_packages
                message += str(total_bk_pkg)
                message += " Cajas \n"
                message += "quedan por validar '" + str(total_packages) + "' \n"
            else:
                message += str(total_packages)
                message += " Cajas \n"
            message += "Cuantas cajas deseas Transferir."

            res.update({
                'picking_id': picking.id,
                'total_packages': total_packages,
                'message': message,
            })

        return res

    @api.multi
    @api.constrains('packages_to_validate')
    def _check_reconcile(self):
        for move_line in self:
            if move_line.packages_to_validate > move_line.total_packages:
                raise ValidationError(
                    'Transfer Package size must not be greater than the total number of pending boxes to be confirmed')

    def fill_packages(self):
        move_line_ids = self.picking_id.move_line_ids.sorted(reverse=True)
        # for mv_line in move_line_ids:
        #     mv_line.qty_done = 0
        for index in range(0, self.packages_to_validate):
            move_line_ids[index].qty_done = move_line_ids[index].product_uom_qty
        return {'type': 'ir.actions.client', 'tag': 'reload'}
