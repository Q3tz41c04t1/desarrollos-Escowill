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


class StockPicking(models.Model):

    _inherit = 'stock.picking'

    date_scheduled = fields.Date(string="Schedule Date")

    # Server action method to fill sale_id to invoices for old records
    def set_scheduled_date(self):
        pickings = self.env['stock.picking'].search([
            ('date_scheduled', '=', False),
            ('scheduled_date', '!=', False)])

        for picking in pickings:
            picking.date_scheduled = picking.scheduled_date.date()

    @api.model
    def create(self, vals):
        res = super(StockPicking, self).create(vals)
        if res.scheduled_date:
            res.date_scheduled = res.scheduled_date.date()
        return res

    def write(self, vals):
        if vals.get('scheduled_date'):
            vals['date_scheduled'] = vals.get('scheduled_date').date()
        return super(StockPicking, self).write(vals)
