# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'BIAS Base Reports',
    'author': 'OpenBias',
    'website': 'http://bias.com.mx',
    'category': 'Localization',
    'description': """
Dieses  Modul beinhaltet einen deutschen Kontenrahmen basierend auf dem SKR03.
==============================================================================
Reports and localization.
    """,
    'depends': ['base', 'web', 'account'],
    'data': [
        'data/report_paperformat_views.xml',
        'data/report_template.xml',
        'data/report_layout.xml',
        'data/cfd_data.xml',
        'views/webclient_templates.xml',
        'wizard/report_xlsx_wiz_views.xml',
        'report/report_account_move.xml',
    ],
    'demo': [
        'demo/report_demo_partner_xlsx_data.xml',
    ],
    'installable': True,
}
