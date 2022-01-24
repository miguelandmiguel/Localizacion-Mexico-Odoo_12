# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import api, fields, models, SUPERUSER_ID, _

class CfdiCartaporte(models.Model):
    _name = 'cfdi.cartaporte.tiposfigura'
    _description = "Carta Porte Tipos Figura"

    cfdi_figuratransporte_tipofigura_id = fields.Many2one(
        'cfdi.cartaporte.figuratransporte',
        string="Tipo Figura",
        help=u"Atributo requerido para registrar la clave de la figura de "
            u"transporte  que  interviene  en  el  traslado  de  los  bienes "
            u"y/o mercancías.")
    cfdi_figuratransporte_figura_id = fields.Many2one(
        'res.partner',
        string="Figura Transporte",
        help=u"Nodo condicional para indicar los datos del(los) tipo(s) de figura(s) "
            u"que participan en el traslado de los bienes y/o mercancías en los "
            u"distintos medios de transporte")
    name = fields.Char(related="cfdi_figuratransporte_tipofigura_id.clave", string='Descripcion')
    sequence = fields.Integer(string='sequence')
    cartaporte_id = fields.Many2one('cfdi.cartaporte', string='CFDI Carta Porte', ondelete='cascade', index=True)