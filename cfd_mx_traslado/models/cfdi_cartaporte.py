# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT


# Modelos
# cfdi_cartaporte_transporte
class CfdiCartaporte(models.Model):
    _name = 'cfdi.cartaporte'
    _description = "CFDI Carta Porte"

    name = fields.Char(string='Nombre', default="Nuevo")
    traslado_id = fields.Many2one('cfdi.traslados', string='Traslado',
      help='The internal user in charge of this contact.')
    cfdi_require_cartaporte = fields.Boolean("Requiere CartaPorte")

    cfdi_cartaporte_tipo = fields.Selection([
            (u'01', u'Autotransporte'),
            (u'02', u'Transporte Marítimo'),
            (u'03', u'Transporte Aéreo'),
            (u'04', u'Transporte Ferroviario')
        ], string="Tipo Carta Porte", default="01")
    cfdi_cartaporte_transpinter = fields.Selection([
            (u'Sí', u'Sí'),
            (u'No', u'No')
        ], string="Transporte Internacional",
        help="Atributo requerido para expresar si los bienes o mercancias que son"
             "transportadas ingresan o salen del territorio nacional.")

    # Entrada / Salida internacional
    cfdi_cartaporte_entradasalidamerc = fields.Selection([
            ('Entrada', 'Entrada'),
            ('Salida', 'Salida')
        ], string="Entrada/Salida Mercancia",
        help="Atributo condicional para precisar si los bienes o mercancias ingresan o"
             "salen del territorio nacional.")
    cfdi_cartaporte_paisorgdest_id = fields.Many2one('res.country', string='PaisOrigenDestino', 
        help="Atributo condicional para registrar la clave del país de "
             "origen  o  destino  de los  bienes  y/o  mercancías  que  se "
             "trasladan a través de los distintos medios de transporte.")
    cfdi_clavetransporte_id = fields.Many2one(
        'cfdi.cartaporte.clavetransporte',
        string="Via Entrada/Salida",
        help="Atributo condicional para precisar la vía de ingreso o salida de los bienes o"
             "mercancías en territorio nacional")
    cfdi_clavetransporte_clave = fields.Char(related='cfdi_clavetransporte_id.clave', store=True, readonly=True, copy=False)

    cfdi_cartaporte_totaldistrec = fields.Float(string="Total Distancia Recorrida", 
        help=u"Atributo condicional para indicar en kilómetros, la suma "
             u"de las distancias recorridas, registradas en el atributo "
             u"'DistanciaRecorrida', para el traslado de los bienes y/o "
             u"mercancías.")

    cfdi_ubicaciones_ids = fields.One2many('cfdi.cartaporte.ubicaciones', 'cartaporte_id', string='Carta Porte Ubicaciones', copy=False)

    # Mercancias
    cfdi_pesobrutototal = fields.Float(
        string="Peso Bruto Total",
        help="Atributo requerido para expresar el peso total bruto de los bienes o"
             "mercancias que se trasladan")
    cfdi_unidadpeso_id = fields.Many2one(
        'cfdi.cartaporte.unidadpeso', string='Unidad Peso',
        help=u"Atributo requerido para registrar la clave de la unidad de "
            u"medida estandarizada del peso de los bienes y/o "
            u"mercancías que se trasladan a través de los distintos "
            u"medios de transporte.")
    cfdi_pesonetototal = fields.Float(
        string="Peso Neto Total",
        help=u"Atributo condicional para registrar la suma de los "
            u"valores indicados en el atributo “PesoNeto” del nodo "
            u"“DetalleMercancia”. ")
    cfdi_numtotalmercancias = fields.Integer(
        string='Num Total Mercancias',
        help="Atributo requerido para expresar el numero total de los bienes o mercancias"
             "que se trasladan en los distintos medios de transporte, identificandose por"
             "cada nodo 'Mercancia' registrado en el complemento.")
    cfdi_cargotasacion = fields.Float(
        string="Cargo Por Tasacion",
        help=u"""Atributo opcional para expresar el importe pagado por la tasación de los
                bienes o mercancías que se trasladan vía aérea.""")
    cfdi_mercancia_ids = fields.One2many('cfdi.cartaporte.mercancias', 'cartaporte_id', string='Carta Porte Mercancias', copy=False, auto_join=True)

    #Autotransporte
    # AutotransporteFederal
    cfdi_transporte_id = fields.Many2one('cfdi.cartaporte.transporte', string="Vehiculos de Transportes")
    cfdi_autotransporte_permsct_id = fields.Many2one(
        'cfdi.cartaporte.tipopermiso',
        string="Permiso SCT",
        help="Atributo requerido para precisar la clave del tipo de permiso proporcionado"
             "por la SCT, el cual debe corresponder de acuerdo al tipo de autotransporte"
             "utilizado para el traslado de los bienes o mercancias registrado en el catalogo"
             "catCartaPorte:c_TipoPermiso")
    cfdi_autotransporte_numpermisosct = fields.Char(
        string="Num. Permiso SCT", size=50,
        help=u"Atributo  requerido  para  registrar  el  número  del  permiso "
            u"otorgado  por  la  SCT  o  la  autoridad  correspondiente,  al "
            u"autotransporte utilizado para el traslado de los bienes y/o "
            u"mercancías.")
    cfdi_autotransporte_configvehicular_id = fields.Many2one(
        'cfdi.cartaporte.configvehicular',
        string="Identificacion Vehicular",
        help="Atributo requerido para expresar la clave de nomenclatura del autotransporte"
             "que es utilizado para transportar los bienes o mercancías..")
    cfdi_autotransporte_placavm = fields.Char(
        string="Placa Vehicular",
        help="Atributo requerido para expresar la clave de nomenclatura del autotransporte"
             "que es utilizado para transportar los bienes o mercancias")
    cfdi_autotransporte_aniomodelovm = fields.Integer(
        string=u"Año del Modelo",
        help=u"Atributo requerido para registrar el año del autotransporte que es utilizado"
             u"para transportar los bienes o mercancías")
    cfdi_autotransporte_nombreaseg = fields.Char(
        string="Asegura Resp. Civil", size=50,
        help="Atributo requerido para expresar el nombre de la aseguradora que cubre los"
             "riesgos del autotransporte utilizado para el traslado de los bienes o"
             "mercancias")
    cfdi_autotransporte_polizaeaseg = fields.Char(
        string="Poliza Resp. Civil", size=30,
        help=u"Atributo  requerido  para  registrar  el  número  de  póliza "
            u"asignado por la aseguradora, que cubre los riesgos por "
            u"responsabilidad civil del autotransporte utilizado para el "
            u"traslado de los bienes y/o mercancías.")
    cfdi_autotransporte_aseguramedambiente = fields.Char(
        string="Asegura Med Ambiente", size=50,
        help=u"Atributo  condicional  para  registrar  el nombre  de  la "
            u"aseguradora,  que  cubre  los  posibles  daños  al  medio "
            u"ambiente (aplicable para los transportistas de "
            u"materiales, residuos o remanentes y desechos "
            u"peligrosos)")
    cfdi_autotransporte_polizamedambiente = fields.Char(
        string="Poliza Med Ambiente", size=30,
        help=u"Atributo condicional para registrar el número de póliza "
            u"asignado  por  la  aseguradora,  que  cubre  los  posibles "
            u"daños al medio ambiente (aplicable para los "
            u"transportistas  de  materiales,  residuos  o  remanentes  y "
            u"desechos peligrosos). ")
    cfdi_autotransporte_aseguracarga = fields.Char(
        string="Asegura Carga", size=50,
        help=u"Atributo opcional para registrar el nombre de la "
            u"aseguradora que cubre los riesgos de la carga (bienes "
            u"y/o  mercancías)  del  autotransporte  utilizado  para  el "
            u"traslado. ")
    cfdi_autotransporte_polizacarga = fields.Char(
        string="Poliza Carga", size=30,
        help=u"Atributo  opcional  para  expresar  el  número  de  póliza "
            u"asignado por la aseguradora que cubre los riesgos de "
            u"la  carga  (bienes  y/o  mercancías)  del  autotransporte "
            u"utilizado para el traslado.")
    cfdi_autotransporte_primaseguro = fields.Float(
        string="Prima Seguro", size=30,
        help=u"Atributo opcional para registrar el valor del importe por "
            u"el cargo adicional convenido entre el transportista y el "
            u"cliente, el cual será igual al valor de la prima del seguro "
            u"contratado,  conforme  a  lo  establecido  en  la  cláusula "
            u"novena del Acuerdo por el que se homologa la Carta de "
            u"Porte  regulada  por  la  Ley  de  Caminos,  Puentes  y "
            u"Autotransporte Federal, con el complemento Carta "
            u"Porte  que  debe  acompañar  al  Comprobante  Fiscal "
            u"Digital por Internet (CFDI).")

    cfdi_autotransporte_subtiporem_id = fields.Many2one(
        'cfdi.cartaporte.subtiporemolque',
        string="Subtipo Remolque",
        help="Atributo requerido para expresar la clave del subtipo de remolque o"
             "semirremolques que se emplean con el autotransporte para el traslado de los"
             "bienes o mercancias.")
    cfdi_autotransporte_placa = fields.Char(
        string=u"Placa",
        help=u"Atributo requerido para registrar el valor de la placa vehicular del remolque o"
             "semirremolque que es utilizado para transportar los bienes o mercancias, se"
             "deben registrar solo los caracteres alfanumericos, sin guiones y espacios")
    cfdi_autotransporte_subtiporem02_id = fields.Many2one(
        'cfdi.cartaporte.subtiporemolque',
        string="Subtipo Remolque 2",
        help="Atributo requerido para expresar la clave del subtipo de remolque o"
             "semirremolques que se emplean con el autotransporte para el traslado de los"
             "bienes o mercancias.")
    cfdi_autotransporte_placa02 = fields.Char(
        string=u"Placa 2",
        help=u"Atributo requerido para registrar el valor de la placa vehicular del remolque o"
             "semirremolque que es utilizado para transportar los bienes o mercancias, se"
             "deben registrar solo los caracteres alfanumericos, sin guiones y espacios")

    # FiguraTransporte
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

    # Figura Transporte:
    cfdi_tiposfigura_ids = fields.One2many('cfdi.cartaporte.tiposfigura', 'cartaporte_id', string='Carta Porte Tipos Figura', copy=False)

    
    def getDatasCartaPorteMercancias(self):
        return {}





