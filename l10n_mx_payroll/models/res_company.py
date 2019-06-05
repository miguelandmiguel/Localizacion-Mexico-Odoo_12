# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _

class ResCompany(models.Model):
    _inherit = "res.company"
    
    # cfdi_curp = fields.Char(string="CURP", oldname="curp", help="Llenar en caso de que el empleador sea una persona física")
    # cfdi_registropatronal_id = fields.Many2one('l10n_mx_payroll.regpat', string='Registro patronal', oldname='registro_patronal_id')
    cfdi_registropatronal_id = fields.Char(string="Registro patronal", help="")
    cfdi_riesgo_puesto_id = fields.Many2one("l10n_mx_payroll.riesgo_puesto", string="Clase riesgo", oldname="riesgo_puesto_id")
    
