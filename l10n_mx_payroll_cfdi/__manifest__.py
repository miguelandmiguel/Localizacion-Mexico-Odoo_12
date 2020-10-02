# -*- coding: utf-8 -*-
{
    'name': "l10n_mx_payroll_cfdi",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """
        Long description of module's purpose
    """,
    'author': "OpenBias",
    'website': "https://bias.com.mx",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base_setup', 'hr', 'hr_payroll', 'hr_payroll_account', 'l10n_mx_payroll'],
    'data': [
        'data/cfdi.xml',
        # 'security/ir.model.access.csv',
        'views/hr_payslip_views.xml',
        'report/report_menu_xml.xml',
    ]
}