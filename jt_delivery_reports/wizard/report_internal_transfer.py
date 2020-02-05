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
import base64
from odoo.exceptions import ValidationError


class InternalTransferReport(models.TransientModel):

    _name = 'tran.rep.wiz'
    _description = 'Internal Transfer Report'

    source_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Almacén Origen")
    dest_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Almacén Destino")
    date = fields.Datetime(string="Fecha del movimiento")
    move_ids = fields.Many2many(
        'tran.rep.wiz.line', 'wiz_id')
    all_select = fields.Boolean(string="Select All")

    state = fields.Selection([
        ('choose', 'choose'),
        ('get', 'get')], default='choose')
    report = fields.Binary('Prepared file', readonly=True)
    name = fields.Char('File Name', size=100)

    def return_wizard(self):
        # Return to wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tran.rep.wiz',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    @api.onchange('all_select')
    def _onchange_all_select(self):
        if self.all_select:
            for line in self.move_ids:
                line.to_print = True
        else:
            for line in self.move_ids:
                line.to_print = False

    def fill_move_lines(self):
        self.move_ids = False
        if not self.source_warehouse_id or not self.dest_warehouse_id or not self.date:
            raise ValidationError('Please fill all the fields')
        else:
            picking_type_ids = []
            if self.source_warehouse_id and self.source_warehouse_id.int_type_id:
                picking_type_ids.append(self.source_warehouse_id.int_type_id.id)
            if self.dest_warehouse_id and self.dest_warehouse_id.int_type_id:
                picking_type_ids.append(self.dest_warehouse_id.int_type_id.id)
            src_location_ids = self.env['stock.location'].sudo().search(
                [('company_id', '=', self.source_warehouse_id.company_id.id)]).ids
            res_location_ids = self.env['stock.location'].sudo().search(
                [('company_id', '=', self.dest_warehouse_id.company_id.id)]).ids

            move_ids = self.env['stock.picking'].search([
                ('picking_type_id', 'in', picking_type_ids),
                ('scheduled_date', '>', self.date),
                ('location_id', 'in', src_location_ids),
                ('location_dest_id', 'in', res_location_ids)]).mapped('move_ids_without_package')

            vals = []
            for move in move_ids:
                vals.append((0, 0, {'move_id': move.id}))
            self.write({'move_ids': vals})

            return self.return_wizard()

    # Function to generate PDF report
    @api.multi
    def generate_int_report(self):
        self.ensure_one()

        # Count Total Selected lines
        selected_move_ids = []
        for move in self.move_ids:
            if move.to_print:
                selected_move_ids.append(move.move_id.id)

        if not self.source_warehouse_id or not self.dest_warehouse_id or not self.date:
            raise ValidationError('Please fill all the fields')
        elif len(self.move_ids.ids) == 0:
            raise ValidationError(
                'Sorry! There are no any lines to print for selected data')
        elif len(selected_move_ids) == 0:
            raise ValidationError(
                'Please select product lines to print!')
        else:
            report = self.env.ref(
                'jt_delivery_reports.int_transfer_order_report')
            pdf = report.sudo().render_qweb_pdf(selected_move_ids)

            # Store report as PDF so user can download
            out = base64.b64encode(pdf[0])
            self.write({
                'state': 'get',
                'report': out,
                'name': "Package_Internal_Transfers_Report.pdf",
            })
            return self.return_wizard()


class IntMoveLines(models.TransientModel):

    _name = 'tran.rep.wiz.line'
    _description = 'Internal Transfer Product Lines'

    wiz_id = fields.Many2one('tran.rep.wiz')
    move_id = fields.Many2one('stock.move', string='Stock Move')
    picking_id = fields.Many2one(
        'stock.picking', related="move_id.picking_id", string="Transfer Document", store=True)
    to_print = fields.Boolean(string="Print?")
    reference = fields.Char(related="move_id.reference",
                            string="Referencia", store=True)
    product_id = fields.Many2one(
        'product.product', related="move_id.product_id", string="Producto", store=True)
    location_id = fields.Many2one(
        'stock.location', related="move_id.location_id", string="Ubicacion Origen", store=True)
    location_dest_id = fields.Many2one(
        'stock.location', related="move_id.location_dest_id", string="Ubicacion Destino", store=True)
    partner_id = fields.Many2one(
        'res.partner', related="picking_id.partner_id", string="Cliente", store=True)
    date = fields.Datetime(related="picking_id.date_done",
                           string="Fecha de la transferencia", store=True)
