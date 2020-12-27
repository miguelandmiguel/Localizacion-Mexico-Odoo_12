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
    'version': '1.7',
    'depends': ['base_setup', 'hr', 'hr_payroll', 'hr_payroll_account', 'l10n_mx_payroll'],
    'data': [
        'views/report_templates.xml',
        'data/data_report.xml',
        'data/cfdi.xml',
        'report/report_menu_xml.xml',
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/rule_input_code_views.xml',
        'data/mail_template_data.xml',
    ],
    'installable': True,
    'application': False,
}