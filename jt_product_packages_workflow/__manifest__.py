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

{
    'name': 'Product Packages Developement and Labels Printing',
    'summary': 'Generation of packages automatically and printing of packages labels',
    'version': '12.0.0.1.0',
    'category': 'product',
    'author': 'Jupical Technologies Pvt. Ltd.',
    'maintainer': 'Jupical Technologies Pvt. Ltd.',
    'website': 'http://www.jupical.com',
    'license': 'AGPL-3',
    'depends': ['mrp', 'delivery_barcode'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'reports/mrp_report.xml',
        'views/packages_sequence.xml',
        'views/sale_view.xml',
        'views/stock_picking_view.xml',
        'wizard/print_separate_label_wizard_view.xml',
        'wizard/barcode_deliver_product_wizard_view.xml',
        'views/mrp_production_view.xml',
        'views/stock_quant_view.xml',
        'views/update_old_picking_rec_cron.xml',
        'views/package_sequence_view.xml',
        'wizard/wiz_assign_agent_view.xml',
    ],
    'qweb': ['static/src/xml/stock_barcode_template.xml'],
    'application': False,
    'installable': True,
    'auto_install': False,
}
