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
    'version': '1.24',
    'depends': ['base_setup', 'hr', 'hr_payroll', 'account', 'l10n_mx_payroll'],
    'data': [
        'views/report_templates.xml',
        'data/data_report.xml',
        'data/cfdi.xml',
        'report/report_menu_xml.xml',
        'report/report_educarte.xml',
        'security/ir.model.access.csv',
        'views/hr_payroll_account_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_bank_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payroll_structure_views.xml',
        'views/rule_input_code_views.xml',
        'data/mail_template_data.xml',
        'wizard/hr_payslip_employees_views.xml',
        'wizard/hr_payslip_message_wizard_views.xml',
        'wizard/hr_payslip_run_import_inputs_views.xml',
        'wizard/hr_payslip_run_report_educarte_views.xml',
        'views/hr_payslip_reports_views.xml'
    ],
    'installable': True,
    'application': False,
}