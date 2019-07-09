# -*- coding: utf-8 -*-
from odoo import http

# class ConnectionTool(http.Controller):
#     @http.route('/connection_tool/connection_tool/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/connection_tool/connection_tool/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('connection_tool.listing', {
#             'root': '/connection_tool/connection_tool',
#             'objects': http.request.env['connection_tool.connection_tool'].search([]),
#         })

#     @http.route('/connection_tool/connection_tool/objects/<model("connection_tool.connection_tool"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('connection_tool.object', {
#             'object': obj
#         })