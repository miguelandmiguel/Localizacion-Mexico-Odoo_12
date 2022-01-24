# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import api, fields, models, SUPERUSER_ID, _

class CartaPorteEstaciones(models.Model):
    _name = 'cfdi.cartaporte.estaciones'
    _description = 'Estaciones'

    name = fields.Char(string='Descripcion')
    clave = fields.Char(string='Clave')
    nacionalidad = fields.Char(string='Nacionalidad')
    designador_iata = fields.Char(string='Designador IATA')
    linea_ferrea = fields.Char(string='Linea ferrea')
    clavetransporte_id = fields.Many2one(
        'cfdi.cartaporte.clavetransporte',
        string="Via Entrada/Salida",
        help="Atributo condicional para precisar la vía de ingreso o salida de los bienes o"
             "mercancías en territorio nacional")

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
