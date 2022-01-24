# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import api, fields, models, SUPERUSER_ID, _

class CartaPorteConfigVehicular(models.Model):
    _name = 'cfdi.cartaporte.configvehicular'
    _description = 'Config Vehicular'

    name = fields.Char(string='Descripcion')
    clave = fields.Char(string='Clave')

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('clave', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()

    @api.multi
    @api.depends('name', 'clave')
    def name_get(self):
        result = []
        for rec in self:
            name = '[%s] %s'%(rec.clave, rec.name)
            result.append((rec.id, name))
        return result
