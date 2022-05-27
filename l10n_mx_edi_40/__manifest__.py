# -*- coding: utf-8 -*-
{
    'name': 'EDI for Mexico SAT 4.0',
    'version': '1.4',
    'category': 'Hidden',
    'summary': 'Mexican Localization for EDI documents',
    'description': """
EDI Mexican Localization
========================
Allow the user to generate the EDI document for Mexican invoicing.

This module allows the creation of the EDI documents and the communication with the Mexican certification providers (PACs) to sign/cancel them.
    """,
    'author': "OpenBias",
    'website': "https://bias.com.mx",
    'depends': ['base'],
    'data': [
        "data/config_parameter_cfdi_version.xml",
        # 'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
    ]
}