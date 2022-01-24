# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.osv import expression

class resPartner(models.Model):
    _inherit = 'res.partner'

    mum_licencia = fields.Char(
        string=u'Número Licencia', size=16,
        help=u"Atributo condicional para expresar el número de folio de la licencia o el"
             u"permiso otorgado al operador del autotransporte de carga federal en el que"
             u"se trasladan los bienes o mercancías")
    cartaporte_refubicacion = fields.Char(
        string='Referencia Ubicacion',
        help="Atributo opcional para expresar una referencia geografica adicional que"
             "permita una facil o precisa ubicacion del domicilio del origen y/o destino de"
             "las mercancias que se trasladan en los distintos medios de transporte; por"
             "ejemplo, las coordenadas GPS.")


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _load_xsd_complements(self, content):
        complements = [
            ['http://www.sat.gob.mx/CartaPorte20',
             'http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte20.xsd']
        ]
        for complement in complements:
            xsd = {'namespace': complement[0], 'schemaLocation': complement[1]}
            node = etree.Element('{http://www.w3.org/2001/XMLSchema}import', xsd)
            content.insert(0, node)
        content = super(ResCompany, self)._load_xsd_complements(content=content)
        return content

class L10nMxEdiResLocality(models.Model):
    _inherit = 'l10n_mx_edi.res.locality'

    def name_get(self):
        # OVERRIDE
        return [(locl.id, "%s %s" % (locl.code, locl.name or '')) for locl in self]


class ResCity(models.Model):
    _inherit = 'res.city'

    def name_get(self):
        # OVERRIDE
        return [(locl.id, "%s %s" % (locl.l10n_mx_edi_code, locl.name or '')) for locl in self]

