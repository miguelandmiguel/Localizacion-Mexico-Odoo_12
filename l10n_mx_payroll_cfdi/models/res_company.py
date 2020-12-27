# -*- coding: utf-8 -*-

from odoo import _, api, fields, models, tools

class ResCompany(models.Model):
    _inherit = 'res.company'

    bank_banorte_id = fields.Many2one('res.partner.bank', string='Banco Banorte')
    clave_emisora = fields.Char(string="clave_emisora", size=5)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_partner_id = fields.Many2one(related='company_id.partner_id')
    bank_banorte_id = fields.Many2one(related='company_id.bank_banorte_id', readonly=False, string='Banco Banorte')
    clave_emisora = fields.Char(related='company_id.clave_emisora', readonly=False, string="clave_emisora", size=5)

