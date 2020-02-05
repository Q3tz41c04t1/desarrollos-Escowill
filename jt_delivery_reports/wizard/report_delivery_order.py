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


class DeliveryOrderReport(models.TransientModel):

    _name = 'del.rep.wiz'
    _description = 'Delivery Order Report'

    date = fields.Date()
    partner_id = fields.Many2one('res.partner')
    order_id = fields.Many2one('sale.order')

    state = fields.Selection(
        [('choose', 'choose'), ('get', 'get')], default='choose')
    report = fields.Binary('Prepared file', readonly=True)
    name = fields.Char('File Name', size=100)

    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            pickings = self.env['stock.picking'].search([
                ('picking_type_code', '=', 'outgoing'),
                ('date_scheduled', '=', self.date),
                ('sale_id', '!=', False)])
            partner_ids = pickings.mapped('partner_id').ids
            return {'domain': {'partner_id': [('id', 'in', partner_ids)]}}

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.date and self.partner_id:
            orders = self.env['sale.order'].search([
                ('state', 'not in', ['draft', 'sent']),
                ('init_date', '=', self.date),
                ('partner_id', '=', self.partner_id.id),
                ('picking_ids', '!=', False)])
            return {'domain': {'order_id': [('id', 'in', orders.ids)]}}

    # Function to generate PDF report
    @api.multi
    def generate_order_report(self):
        self.ensure_one()
        if self.date and self.partner_id and self.order_id:
            context = {
                'customer': self.partner_id,
                'order_id': self.order_id,
                'date': self.date,
            }
            pickings = self.env['stock.picking'].search([
                ('picking_type_code', '=', 'outgoing'),
                ('date_scheduled', '=', self.date),
                ('sale_id', '=', self.order_id.id),
                ('partner_id', '=', self.partner_id.id)])

            report = self.env.ref('jt_delivery_reports.delivery_order_report')
            pdf = report.with_context(context).render_qweb_pdf(pickings.ids)
            # Store report as PDF so user can download
            out = base64.b64encode(pdf[0])
            self.write({
                'state': 'get',
                'report': out,
                'name': "Package_Delivery_Order_Report.pdf",
            })

            # Return to wizard
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'del.rep.wiz',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'new',
            }
