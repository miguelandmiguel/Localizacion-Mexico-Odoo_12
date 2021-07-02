# -*- coding: utf-8 -*-

from werkzeug import url_quote
from os.path import join
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo import _, api, fields, models, tools

import base64
from lxml import etree, objectify
from lxml.objectify import fromstring


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_amece_alternateid = fields.Char(
        string='Alternate Identification (Amece) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)')
    l10n_mx_edi_amece_gln = fields.Char(
        string='Numero Global de Localización (GLN) ',
        help='Identificacion del proveedor (numero de proveedor asignado por el comprador)', size=13)    

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_amece_alternateid = fields.Char(
        related='company_id.l10n_mx_edi_amece_alternateid', readonly=False,
        string='Alternate Identification (Amece) *')
    l10n_mx_edi_amece_gln = fields.Char(
        related='company_id.l10n_mx_edi_amece_gln', readonly=False,
        string='Numero Global de Localización (GLN) Amece *')



class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def l10n_mx_edi_amece_is_required(self):
        addenda_amece = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        return (True if addenda.id == addenda_amece.id else False)

    @api.one
    def _compute_edi_amece_addenda(self):
        self.l10n_mx_edi_amece_addenda = self.l10n_mx_edi_amece_is_required()

    l10n_mx_edi_amece_addenda = fields.Boolean(string='Add Amece Addenda', readonly=True, compute='_compute_edi_amece_addenda')
    l10n_mx_edi_amece_referenceidentification = fields.Char(string='Numero de pedido (comprador) ')
    l10n_mx_edi_amece_referencedate = fields.Date(string='Fecha del Pedido ')
    l10n_mx_edi_amece_additionalinformation = fields.Char(string='Numero de aprobacion')
    l10n_mx_edi_amece_personordepartmentname = fields.Char(string='Contacto de Compras')

    l10n_mx_edi_amece_shipto_id = fields.Many2one('res.partner', string='Entrega Mercancia ')

    def getshipTostreetAddressOne(self, shipTo=False):
        streetAddressOne = '%s %s %s'%(shipTo.street_name or '', shipTo.street_number  or '', shipTo.l10n_mx_edi_colony  or '')
        return streetAddressOne

    def getAddendaSumary(self):
        cfdi = self.l10n_mx_edi_get_xml_etree()
        Serie = cfdi.get('Serie') if cfdi is not None else None
        Folio = cfdi.get('Folio') if cfdi is not None else None        
        Total = cfdi.get('Total') if cfdi is not None else None
        SubTotal = cfdi.get('SubTotal') if cfdi is not None else None
        Descuento = cfdi.get('Descuento', 0.0) if cfdi is not None else None
        TipoCambio = cfdi.get('TipoCambio', '1.000000') if cfdi is not None else None
        TotalImpuestosTrasladados = cfdi.Impuestos.get('TotalImpuestosTrasladados') or 0.0
        return {
            'serie': Serie,
            'folio': Folio,
            'totalAmount': Total or 0.0,
            'baseAmount': SubTotal or 0.0,
            'taxAmount': TotalImpuestosTrasladados or 0.0,
            'descuento': Descuento
        }

    @api.multi
    def action_generate_addendaammece(self):
        self.ensure_one()
        addenda = self.env.ref('l10n_mx_addenda_amece.l10n_mx_edi_addenda_amece', raise_if_not_found=False)
        if not addenda:
            return True
        values = {
            'record': self,
        }
        addenda_node_str = addenda.render(values=values).strip()
        if not addenda_node_str:
            return True
        addenda_node = fromstring(addenda_node_str)
        if addenda_node.tag != '{http://www.sat.gob.mx/cfd/3}Addenda':
            node = etree.Element(etree.QName(
                'http://www.sat.gob.mx/cfd/3', 'Addenda'))
            node.append(addenda_node)
            addenda_node = node
        cfdi = self.l10n_mx_edi_get_xml_etree()
        cfdi.Addenda = addenda_node
        xml_signed = base64.encodestring(etree.tostring( cfdi, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        attachment_id.write({
            'datas': xml_signed,
            'mimetype': 'application/xml'
        })
        return True        

class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    def getGrossPrice(self):
        precision_digits = self.currency_id.l10n_mx_edi_decimal_places
        if precision_digits is False:
            raise UserError(_(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough."), self.currency_id)

        subtotal_wo_discount = lambda l: float_round(
            l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
            l.price_unit * l.quantity, int(precision_digits))

        grossPrice = '%.*f' % (precision_digits, subtotal_wo_discount(self)/self.quantity) if self.quantity else 0.0                
        return float(grossPrice)