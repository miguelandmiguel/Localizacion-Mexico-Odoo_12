# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _

# Mercancia => GuiasIdentificacion
class CfdiMercanciaGuias(models.Model):
    _name = 'cfdi.cartaporte.mercancias.guias'
    _description = 'Mercancias Guias Identificacion'

    name = fields.Char(string='Numero Guia Identificacion', 
        help=u"Atributo requerido para expresar el número de guía de "
            u"cada paquete que se encuentra asociado con el "
            u"traslado  de  los  bienes  y/o mercancías  en  territorio "
            u"nacional.")
    sequence = fields.Integer(string='sequence')
    descripcion = fields.Char(string='Descrip Guia Identificacion', 
        help=u"Atributo requerido para expresar la descripción del "
            u"contenido del paquete o carga registrada en la guía, o"
            u"en el número de identificación, que se encuentra "
            u"asociado con el traslado de los bienes y/o mercancías"
            u"dentro del territorio nacional")
    pesoguiaidentificacion = fields.Float(
        string='Peso Guia Identificacion',
        help=u"Atributo  requerido  para  indicar  en  kilogramos,  el  peso "
            u"del paquete o carga que se está trasladando en "
            u"territorio  nacional  y  que  se  encuentra  registrado  en  la "
            u"guía o el número de identificación correspondiente.")
    mercancia_id = fields.Many2one('cfdi.cartaporte.mercancias', string='CFDI Mercancias', ondelete='cascade', index=True)
