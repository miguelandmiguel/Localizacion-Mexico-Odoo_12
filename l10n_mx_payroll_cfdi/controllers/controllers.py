# -*- coding: utf-8 -*-
from odoo import http

# class L10nMxPayrollCfdi(http.Controller):
#     @http.route('/l10n_mx_payroll_cfdi/l10n_mx_payroll_cfdi/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_mx_payroll_cfdi/l10n_mx_payroll_cfdi/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_mx_payroll_cfdi.listing', {
#             'root': '/l10n_mx_payroll_cfdi/l10n_mx_payroll_cfdi',
#             'objects': http.request.env['l10n_mx_payroll_cfdi.l10n_mx_payroll_cfdi'].search([]),
#         })

#     @http.route('/l10n_mx_payroll_cfdi/l10n_mx_payroll_cfdi/objects/<model("l10n_mx_payroll_cfdi.l10n_mx_payroll_cfdi"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_mx_payroll_cfdi.object', {
#             'object': obj
#         })