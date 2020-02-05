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
    'name': 'Delivery Orders Reports',
    'summary': 'Delivery Orders Reports',
    'version': '12.0.0.1.0',
    'category': 'inventory',
    'author': 'Jupical Technologies Pvt. Ltd.',
    'maintainer': 'Jupical Technologies Pvt. Ltd.',
    'website': 'http://www.jupical.com',
    'license': 'AGPL-3',
    'depends': [
        'jt_delivery_transfer'
    ],
    'data': [
        'data/data.xml',
        'views/assets.xml',
        'views/menus.xml',
        'report/delivery_order_report.xml',
        'report/transfer_report_pdf.xml',
        'wizard/report_delivery_order_view.xml',
        'wizard/report_internal_transfer_view.xml',
    ],
    'qweb': ['static/src/xml/client_action_template.xml'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
