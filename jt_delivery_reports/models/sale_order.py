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


class SaleOrder(models.Model):

    _inherit = 'sale.order'

    init_date = fields.Date(string="Initiation Date")

    # Server action method to fill sale_id to invoices for old records
    def set_create_date(self):
        orders = self.env['sale.order'].search([
            ('init_date', '=', False),
            ('create_date', '!=', False)])

        for order in orders:
            order.init_date = order.create_date.date()

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if res.create_date:
            res.init_date = res.create_date.date()
        return res

    def write(self, vals):
        if vals.get('create_date'):
            vals['init_date'] = vals.get('create_date').date()
        return super(SaleOrder, self).write(vals)
