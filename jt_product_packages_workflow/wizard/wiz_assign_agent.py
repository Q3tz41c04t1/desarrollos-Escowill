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


class AssignComAgentWizard(models.TransientModel):

    _name = 'assign.commercial.agent'
    _description = 'Assign Commercial Agent'

    user_id = fields.Many2one('res.users', string="Commercial Agent")

    @api.constrains('user_id')
    def _check_user_id(self):
        if not self.user_id:
            raise ValidationError("Please Select Commercial Agent To Change!")

    def assign_agent(self):
        context = self.env.context
        quant_ids = context.get('active_ids')

        if self.user_id:
            for quant_id in quant_ids:
                quant = self.env['stock.quant'].sudo().browse(int(quant_id))
                quant.user_id = self.user_id.id
