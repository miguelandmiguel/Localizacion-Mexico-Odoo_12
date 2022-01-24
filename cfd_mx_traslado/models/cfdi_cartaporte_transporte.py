# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT

# Modelos
class CfdiCartaporteTransporte(models.Model):
    _name = 'cfdi.cartaporte.transporte'
    _description = "CFDI Carta Porte"

    name = fields.Char(string='Nombre', default="")
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