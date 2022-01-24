# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _

class CfdiCartaPorteUbicaciones(models.Model):
    _name = 'cfdi.cartaporte.ubicaciones'
    _description = 'Carta Porte Ubicacion'
    _order = "cartaporte_id,sequence,id"

    name = fields.Char(string='Nombre', default="Nuevo")
    sequence = fields.Integer(string='sequence')
    cartaporte_id = fields.Many2one('cfdi.cartaporte', string='CFDI Carta Porte', ondelete='cascade', index=True)


    cfdi_cartaporte_tipo = fields.Selection([
            (u'01', u'Autotransporte'),
            (u'02', u'Transporte Marítimo'),
            (u'03', u'Transporte Aéreo'),
            (u'04', u'Transporte Ferroviario')
        ], string="Tipo Carta Porte", default="01", related='cartaporte_id.cfdi_cartaporte_tipo', store=True, readonly=True, copy=False)
    cfdi_clavetransporte_clave = fields.Char(related='cartaporte_id.cfdi_clavetransporte_clave', store=True, readonly=True, copy=False)

    tipoubicacion = fields.Selection([
        ('Origen', 'Origen'),
        ('Destino', 'Destino'),
    ], help=u'Atributo requerido para precisar si el tipo de ubicación '
         u'corresponde al origen o destino de las ubicaciones para '
         u'el traslado de los bienes y/o mercancías en los distintos '
         u'medios de transporte.', )
    ubicacion_id = fields.Char(string='ID Ubicacion', 
        help=u"Atributo  condicional para  registrar  una  clave que  sirva "
            u"para  identificar  el  punto  de  salida  o  entrada  de  los "
            u"bienes y/o mercancías que se trasladan a través de los "
            u"distintos medios de transporte, la cual estará integrada "
            u"de la siguiente forma: para origen el acrónimo “OR” o "
            u"para  destino  el  acrónimo  “DE”  seguido  de  6  dígitos "
            u"numéricos asignados por el contribuyente que emite el "
            u"comprobante para su identificación.")
    remitentedest_id = fields.Many2one('res.partner', string='Remitente')
    distanciarecorrida = fields.Float(
        string='Distancia Recorrida',
        help="Atributo condicional para registrar la distancia recorrida en kilometros de la"
             "ubicacion de Origen a la de Destino parcial o final, de los distintos medios de"
             "transporte que trasladan los bienes o mercancias")
    numestacion_id = fields.Many2one(
        'cfdi.cartaporte.estaciones',
        string=u'Número de Estación',
        help=u"Atributo condicional para registrar la clave del número de la estación de"
             u"salida por la que se trasladan los bienes o mercancías en los distintos medios"
             u"de transporte, esto de acuerdo al valor de la columna Clave identificación que"
             u"permite asociarla al tipo de transporte.")
    fechahorasaalida = fields.Datetime(string='Fecha-Hora Salida/llegada')
    tipoestacion_id = fields.Many2one(
        'cfdi.cartaporte.tipoestacion',
        string="Tipo Estacion",
        help="Atributo condicional para precisar el tipo de estación por el que pasan los"
             "bienes o mercancías durante su traslado en los distintos medios de"
             "transporte")
    navegaciontrafico = fields.Char(
        string='Tipo Puerto Maritimo',
        help="Atributo condicional para registrar el tipo de puerto por el que se documentan"
             "los bienes o mercancías vía marítima.")  

