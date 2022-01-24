# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import api, fields, models, SUPERUSER_ID, _

class CartaPorteTipoEstacion(models.Model):
    _name = 'cfdi.cartaporte.tipoestacion'
    _description = 'Tipo Estacion'

    name = fields.Char(string='Nombre')
    clave = fields.Char(string='Clave')
    clavetransporte_ids = fields.Many2many('cfdi.cartaporte.clavetransporte', 'cfdiclavetransporte_tipoestacion_rel',
        'clavetransporte_id', 'tipoestacion_id', string='Clave transporte')

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
