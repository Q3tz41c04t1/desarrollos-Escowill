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


class PackageSequence(models.Model):

    _name = 'package.sequence'
    _description = 'Sequencee Packages to store in this model to reuse sequence'
    _rec_name = 'complete_name'

    sale_id = fields.Many2one('sale.order', string='Sale Order')
    sale_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    manufacturing_order_id = fields.Many2one(
        'mrp.production', string="Manufacturing Order")
    sequence = fields.Char(string='Sequance')
    package_name = fields.Char(string='Package Name')
    complete_name = fields.Char(
        string='Complete Name', compute="_compute_complete_name")

    @api.model
    def create(self, vals):
        rec = super(PackageSequence, self).create(vals)
        if rec.manufacturing_order_id and rec.sequence:
            MO_ref = rec.manufacturing_order_id.name.replace('/', '')
            rec.package_name = str(MO_ref).replace('-', '') + rec.sequence
        return rec

    # Compute sequence name
    @api.multi
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = ''
            if rec.manufacturing_order_id and rec.sequence:
                MO_ref = rec.manufacturing_order_id.name.replace('/', '')
                rec.complete_name = str(MO_ref).replace('-', '') + rec.sequence
