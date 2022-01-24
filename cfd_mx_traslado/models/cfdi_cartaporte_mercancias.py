# -*- coding: utf-8 -*-

from odoo.osv import expression
from odoo import api, fields, models, SUPERUSER_ID, _

class CfdiCartaPorteUbicaciones(models.Model):
    _name = 'cfdi.cartaporte.mercancias'
    _description = 'Carta Porte Mercancias'
    _order = "cartaporte_id,sequence,id"

    name = fields.Char(string='Nombre', default="Nuevo")
    sequence = fields.Integer(string='sequence')
    cartaporte_id = fields.Many2one('cfdi.cartaporte', string='CFDI Carta Porte', ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Producto')
    stock_id = fields.Many2one('stock.move', string='Stock')

    bienestransp_id = fields.Many2one(
        'l10n_mx_edi.product.sat.code', string='Bienes Transp',
        help=u"Atributo requerido para registrar la clave de producto de "
            u"los  bienes  y/o  mercancías  que  se  trasladan  en  los "
            u"distintos medios de transporte. ")
    clavestcc_id =  fields.Many2one(
        'cfdi.cartaporte.clavestcc',
        string="ClaveSTCC (Ferroviario)",
        help=u"Atributo opcional para expresar la clave de producto de "
            u"la STCC (por sus siglas en inglés, Standard "
            u"Transportation Commodity Code), cuando el medio de "
            u"transporte utilizado para el traslado de los bienes y/o "
            u"mercancías sea ferroviario.")
    descripcion = fields.Char(
        string='Descripcion',
        help=u"Atributo requerido para detallar las características de "
            u"los bienes y/o mercancías que se trasladan en los "
            u"distintos medios de transporte")
    cantidad = fields.Float(
        string='Cantidad',
        help=u"Atributo requerido para expresar la cantidad total de los "
            u"bienes y/o mercancías que se trasladan a través de los "
            u"distintos medios de transporte.")
    claveunidad_id =  fields.Many2one(
        'l10n_mx_edi.product.sat.code',
        string="Clave Unidad",
        help=u"Atributo requerido para registrar la clave de la unidad de "
            u"medida estandarizada aplicable para la cantidad de los "
            u"bienes y/o mercancías que se trasladan en los distintos "
            u"medios de transporte. La unidad debe corresponder con "
            u"la descripción de los bienes y/o mercancías registrados")
    unidad = fields.Char(
        string='Unidad',
        help=u"Atributo  opcional  para  registrar  la  unidad  de  medida "
            u"propia  para  la  cantidad  de  los  bienes  y/o  mercancías "
            u"que  se  trasladan  a  través  de  los  distintos  medios  de "
            u"transporte. La unidad debe corresponder con la "
            u"descripción de los bienes y/o mercancías.")
    dimensiones = fields.Char(
        string='Dimensiones',
        help=u"Atributo opcional para expresar las medidas del "
            u"empaque de los bienes y/o mercancías que se "
            u"trasladan en los distintos medios de transporte. Se debe "
            u"registrar la longitud, la altura y la anchura en "
            u"centímetros o en pulgadas, separados dichos valores "
            u"con una diagonal, i.e. 30/40/30cm.")

    # Materia Peligroso
    materialpeligroso = fields.Selection([
            (u'Sí', u'Sí'),
            ('No', 'No')
        ], string='Material Peligroso', default="No",
        help=u"Atributo  condicional  para  precisar  que  los  bienes  y/o "
            u"mercancías que se trasladan son considerados o "
            u"clasificados como material peligroso.")
    cvematerialpeligroso_id =  fields.Many2one(
        'cfdi.cartaporte.materialpeligroso',
        string="Clave Material Peligroso",
        help=u"Atributo condicional para indicar la clave del tipo de "
            u"material peligroso que se transporta de acuerdo a la "
            u"NOM-002-SCT/2011")
  
      # Embalaje
    embalaje_id =  fields.Many2one(
        'cfdi.cartaporte.embalaje',
        string="Embalaje",
        help=u"Atributo condicional para precisar la clave del tipo de "
            u"embalaje que se requiere para transportar el material o "
            u"residuo peligroso.")
    descripembalaje = fields.Char(
        string='Descripcion Embalaje',
        help=u"Atributo opcional para expresar la descripción del "
            u"embalaje de los bienes y/o mercancías que se trasladan "
            u"y que se consideran material o residuo peligroso")
    pesoenkg = fields.Float(
        string='Peso KG',
        help=u"Atributo requerido para indicar en kilogramos el peso "
            u"estimado de los bienes y/o mercancías que se trasladan "
            u"en los distintos medios de transporte.")
    valormercancia = fields.Float(
        string='Valor Mercancia',
        help=u"Atributo condicional para expresar el monto del valor de "
            u"los  bienes  y/o  mercancías  que  se  trasladan  en  los "
            u"distintos  medios  de  transporte,  de  acuerdo  al  valor "
            u"mercado, al valor pactado en la contraprestación o bien "
            u"al valor estimado que determine el contribuyente.")
    fraccionarancelaria = fields.Char(
        string='Fraccion Arancelaria',
        help=u"Atributo condicional que sirve para expresar la clave de "
            u"la fracción arancelaria que corresponde con la "
            u"descripción de los bienes y/o mercancías que se "
            u"trasladan en los distintos medios de transporte.")
    uuicomercioext = fields.Char(
        string='UUID Comercio Ext',
        help=u"Atributo opcional para expresar el folio fiscal (UUID) del "
            u"comprobante de comercio exterior que se relaciona")

    pedimento_ids = fields.One2many('cfdi.cartaporte.mercancias.pedimentos', 'mercancia_id', string='Pedimentos Mercancias', copy=False)
    guias_ids = fields.One2many('cfdi.cartaporte.mercancias.guias', 'mercancia_id', string='Guias Mercancias', copy=False)
    cantidadtransporta_ids = fields.One2many('cfdi.cartaporte.mercancias.cantidad', 'mercancia_id', string='Cantidad Transporta', copy=False)
    detalle_ids = fields.One2many('cfdi.cartaporte.mercancias.detalle', 'mercancia_id', string='Detalle Mercancia', copy=False)