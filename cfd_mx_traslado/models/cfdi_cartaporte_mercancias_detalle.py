# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _

# Mercancia => Detalle Mercancia
class CfdiMercanciaDetalle(models.Model):
    _name = 'cfdi.cartaporte.mercancias.detalle'
    _description = 'Mercancias Detalle Mercancias'

    name = fields.Char(string='Detalle Mercancias')
    sequence = fields.Integer(string='sequence')
    unidadpeso_id = fields.Many2one(
        'cfdi.cartaporte.unidadpeso', string='Unidad Peso Merc',
        help=u"Atributo requerido para registrar la clave de la unidad de "
            u"medida estandarizada del peso de los bienes y/o "
            u"mercancías que se trasladan en los distintos medios de "
            u"transporte")
    pesobruto = fields.Float(
        string='Peso Bruto',
        help=u"Atributo requerido para registrar el peso bruto total de "
            u"los bienes y/o mercancías que se trasladan a través de "
            u"los diferentes medios de transporte.")
    pesoneto = fields.Float(
        string='Peso Bruto',
        help=u"Atributo requerido para registrar el peso neto total de los "
            u"bienes y/o mercancías que se trasladan en los distintos "
            u"medios de transporte.")
    pesotara = fields.Float(
        string='Peso Tara',
        help=u"Atributo requerido para registrar el peso bruto, menos el "
            u"peso neto de los bienes y/o mercancías que se "
            u"trasladan a través de los distintos medios de transporte")
    numpiezas = fields.Integer(
        string='Num Piezas',
        help=u"Atributo opcional para registrar el número de piezas de "
            u"los  bienes  y/o  mercancías  que  se  trasladan  en  los "
            u"distintos medios de transporte")
    mercancia_id = fields.Many2one('cfdi.cartaporte.mercancias', string='CFDI Mercancias', ondelete='cascade', index=True)