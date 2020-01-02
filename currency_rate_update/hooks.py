# coding: utf-8

from odoo import api, fields, tools, SUPERUSER_ID

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Currency = env['res.currency']
    token = env['ir.config_parameter'].sudo().get_param('bmx.token', default='')
    if token:
        tipoCambios = Currency.getTipoCambio('2015-01-01', fields.Date.today(), token)
        Currency.refresh_currency(tipoCambios)