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

from odoo import models, api, fields, _
from odoo.exceptions import UserError


class MRPProduction(models.Model):

    _inherit = 'mrp.production'

    sale_id = fields.Many2one('sale.order', string='Sale Order')
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Sale Order Line', compute="_compute_sale_line_id", store=True)
    picking_id = fields.Many2one("stock.picking", "Picking Reference")
    total_packages = fields.Integer(
        string='Total Packages', compute='_compute_total_packages')
    todo_packages = fields.Integer(string='Pending Pick Packages')
    next_package = fields.Integer(string='Next Pick Package')
    todo_pack_packages = fields.Integer(string='Pending Pack Packages')
    next_pack_package = fields.Integer(string='Next Pack Package')
    turno = fields.Char(string='Turno')
    maquina = fields.Char(string='Maquina')
    comm_partner_id = fields.Many2one(
        'res.partner', string='Commercial Partner', domain="[('customer', '=', True)]")
    flag_run_cron = fields.Boolean(string='Flag Run CRON')
    flag_done_production = fields.Boolean(string='Has Done Production?')
    flag_package_stage = fields.Selection([('create', 'Create Package'), ('done', 'Done Package')], default='create')
    flag_pack_package_stage = fields.Selection([('create', 'Create Package'), ('done', 'Done Package')], default='create')
    flag_done_pack_order = fields.Boolean(string="Flag Done Pack Order?")

    @api.multi
    def _compute_comm_agent_id(self):
        for mo in self:
            mo.comm_agent_id = False
            sale_id = mo.sale_id
            if sale_id and sale_id.user_id:
                user_id = sale_id.user_id
                mo.comm_agent_id = user_id.id

    comm_agent_id = fields.Many2one(
        'res.users', string='Commercial Agent', compute='_compute_comm_agent_id')

    # Compute total packages according to qty and package qty
    @api.multi
    def _compute_total_packages(self):
        for order in self:
            order.total_packages = 0
            if order.product_qty and order.sale_line_id:
                line = order.sale_line_id
                pkg_qty = line.product_packaging.qty
                if pkg_qty > 0:
                    order.total_packages = order.product_qty / pkg_qty

    # Function to prepare sequances for package label printing. It calls from
    # qweb report
    def get_sequences(self):
        sequence_lst = []
        total_packages = self.sale_line_id.total_packages
        if total_packages > 0:
            sequences = self.env['package.sequence'].search([
                ('manufacturing_order_id', '=', self.id),
                ('sale_id', '=', self.sale_id.id),
                ('sale_line_id', '=', self.sale_line_id.id)])

            if not sequences:
                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'product_pkg_seq')], limit=1)
                if sequence:
                    sequence.number_next_actual = 1
                for seq in range(0, total_packages):
                    code = self.env['ir.sequence'].next_by_code(
                        'product_pkg_seq')
                    vals = {
                        'sale_id': self.sale_id.id,
                        'sale_line_id': self.sale_line_id.id,
                        'manufacturing_order_id': self.id,
                        'sequence': code,
                    }
                    sequencee = self.env['package.sequence'].create(vals)
                    sequence_lst.append(sequencee.sequence)
                return sequence_lst

            total_sequences = len(sequences)

            if total_sequences == total_packages:
                for sequence in sequences:
                    sequence_lst.append(sequence.sequence)

        return sequence_lst

    def find_order_line(self, order):
        return self.env['sale.order.line'].search([('order_id', '=', order.id), ('product_id', '=', self.product_id.id)], limit=1)

    # To compute sale order line if production created from sale order
    @api.multi
    @api.depends('sale_id')
    def _compute_sale_line_id(self):
        for order in self:
            order.sale_line_id = False
            if order.sale_id:
                line = order.sale_id.order_line.search(
                    [('product_id', '=', order.product_id.id)], limit=1)
                if line:
                    order.sale_line_id = line.id

    # Set sale reference if production created from sale
    @api.model
    def create(self, vals):
        if vals.get('origin'):
            order = self.env['sale.order'].search(
                [('name', '=', vals.get('origin'))], limit=1)
            if order:
                vals['sale_id'] = order.id
                vals['comm_partner_id'] = order.partner_id.id
            else:
                vals['sale_id'] = False

        res = super(MRPProduction, self).create(vals)

        if res.sale_id:
            total_packages = 0
            line = res.find_order_line(res.sale_id)
            pkg_qty = line.product_packaging and line.product_packaging.qty or 0
            if pkg_qty > 0:
                total_packages = res.product_qty / pkg_qty

            res.todo_packages = total_packages
            round_check = res.todo_packages / 1000
            if round_check > 1:
                res.next_package = 1000
            else:
                res.next_package = res.todo_packages
        return res

    # Set sale reference if production created from sale
    @api.multi
    def write(self, vals):
        if vals.get('origin'):
            order = self.env['sale.order'].search(
                [('name', '=', vals.get('origin'))], limit=1)
            if order:
                vals['sale_id'] = order.id
            else:
                vals['sale_id'] = False

        return super(MRPProduction, self).write(vals)

    '''
        - Calls when POST INVENTORY or MARK AS DONE button clicked
        - Send context with sale and production details
    '''
    @api.multi
    def post_inventory(self):
        for order in self:
            moves_not_to_do = order.move_raw_ids.filtered(
                lambda x: x.state == 'done')
            moves_to_do = order.move_raw_ids.filtered(
                lambda x: x.state not in ('done', 'cancel'))
            for move in moves_to_do.filtered(lambda m: m.product_qty == 0.0 and m.quantity_done > 0):
                move.product_uom_qty = move.quantity_done
            moves_to_do._action_done()
            moves_to_do = order.move_raw_ids.filtered(
                lambda x: x.state == 'done') - moves_not_to_do
            order._cal_price(moves_to_do)
            moves_to_finish = order.move_finished_ids.filtered(
                lambda x: x.state not in ('done', 'cancel'))
            if self.sale_id:
                if (self._context.get('final_step')) or (self.check_to_done and not self.consumed_less_than_planned):
                    comm_agent_id = False
                    comm_partner_id = False
                    if order.comm_agent_id:
                        comm_agent_id = order.comm_agent_id.id
                    if order.comm_partner_id:
                        comm_partner_id = order.comm_partner_id.id
                    moves_to_finish.with_context(
                        {
                            'mo': self.id,
                            'production': self,
                            'final_step': True,
                            'comm_agent_id': comm_agent_id,
                            'comm_partner_id': comm_partner_id,
                            'sale_id': self.sale_id.id,
                            'sale_line_id': self.sale_line_id.id,
                            'mo_id': order.name.replace('/', '')
                        })._action_done()
                else:
                    moves_to_finish._action_done()
            else:
                moves_to_finish._action_done()
            order.action_assign()
            consume_move_lines = moves_to_do.mapped('active_move_line_ids')
            for moveline in moves_to_finish.mapped('active_move_line_ids'):
                if moveline.product_id == order.product_id and moveline.move_id.has_tracking != 'none':
                    if any([not ml.lot_produced_id for ml in consume_move_lines]):
                        raise UserError(
                            _('You can not consume without telling for which lot you consumed it'))
                    # Link all movelines in the consumed with same
                    # lot_produced_id false or the correct lot_produced_id
                    filtered_lines = consume_move_lines.filtered(
                        lambda x: x.lot_produced_id == moveline.lot_id)
                    moveline.write(
                        {'consume_line_ids': [(6, 0, [x for x in filtered_lines.ids])]})
                else:
                    # Link with everything
                    moveline.write(
                        {'consume_line_ids': [(6, 0, [x for x in consume_move_lines.ids])]})
        return True

    # Calls when MARK AS DONE button clicked, to send context
    @api.multi
    def button_mark_done(self):
        self.ensure_one()
        for wo in self.workorder_ids:
            if wo.time_ids.filtered(lambda x: (not x.date_end) and (x.loss_type in ('productive', 'performance'))):
                raise UserError(_('Work order %s is still running') % wo.name)
        self._check_lots()
        if self.sale_id:
            self.with_context(final_step=True).post_inventory()
        else:
            self.post_inventory()
        moves_to_cancel = (self.move_raw_ids | self.move_finished_ids).filtered(
            lambda x: x.state not in ('done', 'cancel'))
        moves_to_cancel._action_cancel()
        self.write(
            {'state': 'done', 'date_finished': fields.Datetime.now(), 'flag_run_cron': False})
        return self.write({'state': 'done'})

    @api.multi
    def close_picking_set_owner(self):
        self.ensure_one()

        # new function to split the automated process of MRP close.
        if self.sale_id:
            if self.flag_pack_package_stage == 'create':
                pick_type_id = self.sale_id.warehouse_id and self.sale_id.warehouse_id.pick_type_id and  \
                    self.sale_id.warehouse_id.pick_type_id.id or False
                out_type_id = self.sale_id.warehouse_id and self.sale_id.warehouse_id.out_type_id and \
                    self.sale_id.warehouse_id.out_type_id.id or False
                for move_line in self.finished_move_line_ids:

                    if self.picking_id.picking_type_id.id in [pick_type_id, out_type_id]:
                        self.picking_id.action_assign_owner()
                        if self.sale_id:
                            self.picking_id.with_context(
                                {'mo': self.picking_id.production_id,
                                 'default_production_id': self.picking_id.production_id.id,
                                 'default_user_id': self.comm_agent_id and self.comm_agent_id or False,
                                 'default_sale_id': self.sale_id.id}).button_validate()
                            self.flag_pack_package_stage = 'done'

                            if self.todo_pack_packages != 0:
                                move = self.env['stock.move'].search(
                                    [('picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], limit=1)
                                if move:
                                    todo_list = eval(move.done_line_list)
                                    if len(todo_list) > 0:
                                        todo_list.remove(todo_list[0])
                                        move.done_line_list = str(todo_list)
                            self.todo_pack_packages -= self.next_pack_package
                            # To calculate pick packages
                            round_check = self.todo_pack_packages / 1000
                            if round_check > 1:
                                self.next_pack_package = 1000
                            else:
                                self.next_pack_package = self.todo_pack_packages
            else:
                if self.todo_pack_packages == 0:
                    self.picking_id.write({'date_done': fields.Datetime.now()})
                else:
                    move = self.env['stock.move'].search(
                        [('picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], limit=1)
                    if move:
                        todo_list = eval(move.done_line_list)
                        if len(todo_list) > 0:
                            dest_move = False
                            if len(move.move_dest_ids.ids) > 0:
                                dest_move = move.move_dest_ids[0]
                            if dest_move:
                                dest_move.with_context(flag_validate_pack=True)._action_assign()
                                todo_list.remove(todo_list[0])
                                move.done_line_list = str(todo_list)

                            self.todo_pack_packages -= self.next_pack_package
                            # To calculate pick packages
                            round_check = self.todo_pack_packages / 1000
                            if round_check > 1:
                                self.next_pack_package = 1000
                            else:
                                self.next_pack_package = self.todo_pack_packages
                if self.todo_pack_packages == 0:
                    self.flag_done_production = True
                    self.flag_done_pack_order = True

    def validate_packages(self):
        if self.picking_id and self.sale_line_id and self.sale_line_id.product_packaging:
            move = self.env['stock.move'].search(
                [('picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], limit=1)
            move_line = self.env['stock.move.line'].search([('move_id', '=', move.id), (
                'picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id), ('is_last_line', '=', True)], limit=1)
            if not move_line:
                move_line = self.env['stock.move.line'].search([('move_id', '=', move.id), (
                    'picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], order='id desc',  limit=1)
            if move_line:
                self.picking_id.with_context(flag_validate_package=True, line_id=move_line.id, line_owner_id=self.comm_partner_id and self.comm_partner_id.id or False).button_validate()
            self.flag_package_stage = 'create'
            # To calculate pack packages
            if self.todo_packages == 0:
                self.todo_pack_packages = self.total_packages
                pack_round_check = self.todo_pack_packages / 1000
                if pack_round_check > 1:
                    self.next_pack_package = 1000
                else:
                    self.next_pack_package = self.todo_pack_packages

    def create_packages(self):
        if self.picking_id and self.todo_packages > 0 and self.sale_line_id and self.sale_line_id.product_packaging:
            move = self.env['stock.move'].search(
                [('picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], limit=1)
            if move:
                move_line = self.env['stock.move.line'].search([('move_id', '=', move.id), (
                    'picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id), ('is_last_line', '=', True)], limit=1)
                if not move_line:
                    move_line = self.env['stock.move.line'].search([('move_id', '=', move.id), (
                        'picking_id', '=', self.picking_id.id), ('product_id', '=', self.product_id.id)], order='id desc',  limit=1)
                if move_line:
                    total_pkgs = int(self.next_package)
                    pkg_qty = 0
                    if self.sale_line_id and self.sale_line_id.product_packaging:
                        pkg_qty = self.sale_line_id.product_packaging.qty
                    # Code to create package (Calls Put in pack method)
                    for pkg in range(0, total_pkgs):
                        move_line.qty_done = pkg_qty
                        pkg_no = (int(self.total_packages - self.todo_packages)) + pkg
                        move_line.picking_id.with_context(
                            {'pkg_name': pkg_no + 1, 'mo_id': self.name.replace('/', '')}).put_in_pack()
                    move_line.is_last_line = True
                    self.todo_packages -= self.next_package
                    # To calculate pick packages
                    round_check = self.todo_packages / 1000
                    if round_check > 1:
                        self.next_package = 1000
                    else:
                        self.next_package = self.todo_packages
                    self.flag_package_stage = 'done'
