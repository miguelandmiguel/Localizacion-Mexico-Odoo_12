# -*- coding: utf-8 -*-
{
    'name': "Addenda Amece",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """
        Long description of module's purpose
    """,
    'author': "OpenBias",
    'website': "http://www.bias.com.mx",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['account'],
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
        'views/account_invoice_views.xml',
        'views/addenda_amece.xml',
    ]
}