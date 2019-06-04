# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Mexican Payroll",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """

    """,
    'author': "OpenBias",
    'website': "http://www.bias.com.mx",
    'category': 'Human  Resources',
    'version': '0.1',
    'depends': ['hr_payroll'],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_mx_payroll.tipotrabajador.xml',
        'data/l10n_mx_payroll.tiposueldo.xml',
        'data/l10n_mx_payroll.tipojornada.xml',
        'data/l10n_mx_payroll.tipodescuento.xml',
        'data/l10n_mx_payroll.tipopensionados.xml',
        'data/l10n_mx_payroll.escolaridad.xml',
        'data/l10n_mx_payroll.tipo.xml',
        'data/l10n_mx_payroll.regimen_contratacion.xml',
        'data/l10n_mx_payroll.riesgo_puesto.xml',
        'data/l10n_mx_payroll.origen_recurso.xml',
        'data/l10n_mx_payroll.periodicidad_pago.xml',
        'data/l10n_mx_payroll.tipo_horas.xml',
        "data/l10n_mx_payroll.codigo_agrupador.xml",
        'data/hr.contract.type.xml',
        
        'views/l10n_mx_payroll_views.xml',
        'views/hr_employee_view.xml',
        
        'views/hr_payroll_views.xml',

        'views/l10n_mx_payroll_menuitem.xml'
    ],
}