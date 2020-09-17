# -*- coding: utf-8 -*-

import base64
import logging
import requests

from lxml import etree, objectify
from werkzeug import url_quote
from os.path import join
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, SUPERUSER_ID

_logger = logging.getLogger(__name__)

BODEGA = [
    (1, '[1] BODEGA COPPEL CULIACAN'),
    (2, '[2] BODEGA COPPEL LEON'),
    (3, '[3] BODEGA COPPEL LAGUNA'),
    (6, '[6] BODEGA COPPEL MONTERREY'),
    (7, '[7] BODEGA COPPEL GUADALAJARA'),
    (8, '[8] BODEGA COPPEL AZCAPOTZALCO'),
    (11, '[11] BODEGA COPPEL HERMOSILLO'),
    (12, '[12]] BODEGA COPPEL PUEBLA'),
    (13, '[13] BODEGA COPPEL VILLAHERMOSA'),
    (15, '[15] BODEGA COPPEL IZTAPALAPA'),
    (16, '[16] BODEGA COPPEL IZCALLI'),
    (18, '[18] BODEGA COPPEL IXTAPALUCA'),
    (21, '[21] BODEGA COPPEL DF (TECAMAC)'),
    (22, '[22] BODEGA COPPEL VERACRUZ'),
    (24, '[24] MERIDA'),
    (25, '[25] TLAQUEPAQUE ò  GUADALAJARA II'),
    (27, '[27] TOLUCA')
]

class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_coppel_tipoprov = fields.Char(
        string='Tipo de proveedor Coppel ', default='2',
        help='Tipo de proveedor Coppel')
    l10n_mx_edi_coppel_alternateid = fields.Char(
        string='Alternate Identification (Coppel) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)')
    l10n_mx_edi_coppel_gln = fields.Char(
        string='Numero Global de Localización (GLN) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)', size=13)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_coppel_tipoprov = fields.Char(
        related='company_id.l10n_mx_edi_coppel_tipoprov', readonly=False,
        string='Tipo de proveedor Coppel * ')
    l10n_mx_edi_coppel_alternateid = fields.Char(
        related='company_id.l10n_mx_edi_coppel_alternateid', readonly=False,
        string='Alternate Identification (Coppel) *')
    l10n_mx_edi_coppel_gln = fields.Char(
        related='company_id.l10n_mx_edi_coppel_gln', readonly=False,
        string='Numero Global de Localización (GLN) *')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_coppel_esbodega = fields.Boolean(string="Es Bodega Coopel?")
    l10n_mx_edi_coppel_gln = fields.Char(string='Numero Global de Localización (GLN)', size=13)
    l10n_mx_edi_coppel_bodegaent = fields.Selection(BODEGA, string='Bodega Coppel')