# -*- coding: utf-8 -*-
# from odoo import http


# class L10nMxAddenda(http.Controller):
#     @http.route('/l10n_mx_addenda/l10n_mx_addenda/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_mx_addenda/l10n_mx_addenda/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_mx_addenda.listing', {
#             'root': '/l10n_mx_addenda/l10n_mx_addenda',
#             'objects': http.request.env['l10n_mx_addenda.l10n_mx_addenda'].search([]),
#         })

#     @http.route('/l10n_mx_addenda/l10n_mx_addenda/objects/<model("l10n_mx_addenda.l10n_mx_addenda"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_mx_addenda.object', {
#             'object': obj
#         })
