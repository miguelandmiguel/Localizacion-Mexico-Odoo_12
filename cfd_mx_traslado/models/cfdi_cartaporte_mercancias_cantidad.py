# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _

# Mercancia => Cantidad Transporta
class CfdiMercanciaCantidad(models.Model):
    _name = 'cfdi.cartaporte.mercancias.cantidad'
    _description = 'Mercancias Cantidad Transporta'

    name = fields.Char(string='Cantidad Transporta')
    sequence = fields.Integer(string='sequence')
    cantidad = fields.Float(
        string='Cantidad',
        help=u"Atributo  requerido  para  expresar  el  número  de  bienes "
            u"y/o mercancías que se trasladan en los distintos medios "
            u"de transporte")
    idorigen = fields.Char(string='ID Origen', 
        help=u"Atributo requerido para expresar la clave del "
            u"identificador  del  origen  de  los  bienes  y/o  mercancías "
            u"que se trasladan por los distintos medios de transporte "
            u"de acuerdo al valor registrado en el atributo "
            u"“IDUbicacion”, del nodo “Ubicacion”")
    iddestino = fields.Char(string='ID Destino', 
        help=u"Atributo requerido para registrar la clave del "
            u"identificador del destino de los bienes y/o mercancías "
            u"que se trasladan a través de los distintos medios  de "
            u"transporte, de acuerdo al valor registrado en el atributo "
            u"“IDUbicacion”, del nodo “Ubicacion”")
    clavetransporte_id = fields.Many2one(
        'cfdi.cartaporte.clavetransporte',
        string="Claves Transporte",
        help=u"Atributo condicional para indicar la clave a través de la "
            u"cual se identifica el medio por el que se transportan los "
            u"bienes y/o mercancías")
    mercancia_id = fields.Many2one('cfdi.cartaporte.mercancias', string='CFDI Mercancias', ondelete='cascade', index=True)
