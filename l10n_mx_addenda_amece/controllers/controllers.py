# -*- coding: utf-8 -*-
from odoo import http

# class L10nMxAddendaAmece(http.Controller):
#     @http.route('/l10n_mx_addenda_amece/l10n_mx_addenda_amece/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_mx_addenda_amece/l10n_mx_addenda_amece/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_mx_addenda_amece.listing', {
#             'root': '/l10n_mx_addenda_amece/l10n_mx_addenda_amece',
#             'objects': http.request.env['l10n_mx_addenda_amece.l10n_mx_addenda_amece'].search([]),
#         })

#     @http.route('/l10n_mx_addenda_amece/l10n_mx_addenda_amece/objects/<model("l10n_mx_addenda_amece.l10n_mx_addenda_amece"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_mx_addenda_amece.object', {
#             'object': obj
#         })