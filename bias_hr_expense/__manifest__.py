# -*- coding: utf-8 -*-
{
    'name': "Bias HR Expense",
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
    'depends': ['hr_expense', 'web', 'base'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/hr_expense_views.xml',
    ],
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}