# -*- coding: utf-8 -*-
{
    'name': "Connection Tool",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """
        Long description of module's purpose
    """,
    'author': "OpenBias",
    'website': "http://www.bias.com.mx",
    'category': 'Uncategorized',
    'version': '1.0.2',
    'depends': ['mail', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/action_server_data.xml',
        'views/connection_tool_configure.xml'
    ],
}
