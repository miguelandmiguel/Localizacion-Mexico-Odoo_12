# -*- coding: utf-8 -*-

import base64
import logging
import requests
import pprint

from lxml import etree, objectify
from werkzeug import url_quote
from os.path import join
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, SUPERUSER_ID

_logger = logging.getLogger(__name__)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    l10n_mx_edi_coppel_alternateid = fields.Char(string='Alternate Identification (Coppel) *')
    l10n_mx_edi_coppel_codigo = fields.Char(string='Codigo (Coppel) *')
    l10n_mx_edi_coppel_talla = fields.Char(string='Talla (Coppel) *')





class AccountInvoiceLineCoppel(models.Model):
    _name = 'account.invoice.line.coppel'
    _description = 'Line Coppel'

    name = fields.Char(string="Name")
    line_id = fields.Many2one('account.invoice.line', string="Invoice Line")
    invoice_id = fields.Many2one('account.invoice', string="Invoice")
    
    l10n_mx_edi_coppel_palletqty = fields.Integer(string="Pallet Quantity", default=0)
    l10n_mx_edi_coppel_palletprepactqty = fields.Integer(string="Unidad de Embarque", default=0)
    l10n_mx_edi_coppel_palletdesc = fields.Selection([
        ('EXCHANGE_PALLETS', 'Palet sin Retorno'),
        ('RETURN_PALLETS', 'Palet Retornable'),
        ('PALLET_80x100', 'Palet 80 X 100'),
        ('CASE', 'Cajon'),
        ('BOX', 'Caja')
    ], string="Pallet Description", default='BOX')
    l10n_mx_edi_coppel_palletmethod = fields.Selection([
        ('PREPAID_BY_SELLER', 'Pagado por el proveedor'),
        ('PAID_BY_BUYER', 'Pagado por el comprador'),
    ], string="Method Of Payment", default='PREPAID_BY_SELLER')

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.one
    def _compute_edi_inv_addenda(self):
        addenda = (
            self.partner_id.l10n_mx_edi_addenda or
            self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        add_addenda = False
        if addenda:
            add_addenda = True
        self.l10n_mx_edi_inv_addenda = add_addenda

    @api.one
    @api.depends('invoice_line_ids')
    def _compute_edi_totallotes(self):
        if not self.invoice_line_ids:
            self.l10n_mx_edi_coppel_totallotes = len(self.invoice_line_ids)

    l10n_mx_edi_inv_addenda = fields.Boolean(string='Add Addenda', readonly=True, compute='_compute_edi_inv_addenda')
    l10n_mx_edi_coppel_deliverydate = fields.Date(string='Fecha del mensaje')
    l10n_mx_edi_coppel_refid = fields.Char(string='Numero de Pedido ')
    l10n_mx_edi_coppel_refdate = fields.Date(string='Fecha de Orden de compra ')
    l10n_mx_edi_coppel_shipto_id = fields.Many2one('res.partner', string='Entrega Mercancia ')
    l10n_mx_edi_coppel_refdate = fields.Date(string='Fecha de Orden de compra ')
    l10n_mx_edi_coppel_totallotes = fields.Integer(string='Num Paquetes / Lotes ', store=True, compute='_compute_edi_totallotes', readonly=False)
    coppel_line_ids = fields.One2many('account.invoice.line.coppel', 'invoice_id', string='Coppel Lines', copy=True)    


    def action_generate_linescoppel(self):
        if self.state not in ['draft', 'open']:
            return True
        LineCoppel = self.env['account.invoice.line.coppel']
        for l in self.coppel_line_ids:
            l.unlink()
        for line in self.invoice_line_ids.filtered(lambda inv: not inv.display_type):
            res = LineCoppel.create({
                'name': line.name,
                'line_id': line.id,
                'invoice_id': line.invoice_id.id
            })
        return True


    def cfdi_append_addenda(self, res):
        self.ensure_one()
        addenda = self.partner_id.l10n_mx_edi_addenda

    def getDatasAddendaCoppel(self):
        company_id = self.company_id
        shipTo = self.l10n_mx_edi_coppel_shipto_id or self.partner_shipping_id or self.partner_id

        cfdi = self.l10n_mx_edi_get_xml_etree()
        Serie = cfdi.get('Serie') if cfdi is not None else None
        Folio = cfdi.get('Folio') if cfdi is not None else None
        Moneda = cfdi.get('Moneda') if cfdi is not None else None
        Total = cfdi.get('Total') if cfdi is not None else None
        SubTotal = cfdi.get('SubTotal') if cfdi is not None else None
        TipoCambio = cfdi.get('TipoCambio', '1.000000') if cfdi is not None else None
        TotalImpuestosTrasladados = cfdi.Impuestos.get('TotalImpuestosTrasladados') or 0.0

        lenTotalLotes = 0
        indx = 1
        Conceptos = []
        for line_coppel in self.coppel_line_ids:
            line = line_coppel.line_id or False
            precision_digits = self.currency_id.l10n_mx_edi_decimal_places
            if precision_digits is False:
                raise UserError(_(
                    "The SAT does not provide information for the currency %s.\n"
                    "You must get manually a key from the PAC to confirm the "
                    "currency rate is accurate enough."), self.currency_id)

            lenTotalLotes += 1
            alternateId = line.product_id and line.product_id.l10n_mx_edi_coppel_alternateid or ''

            subtotal_wo_discount = lambda l: float_round(
                l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
                l.price_unit * l.quantity, int(precision_digits))

            grossPrice = '%.*f' % (precision_digits, subtotal_wo_discount(line)/line.quantity) if line.quantity else 0.0
            netPrice = ''
            Conceptos.append({
                'numero': indx,
                'tipo': 'SimpleInvoiceLineItemType',
                'gtin': line.product_id and line.product_id.barcode or '',
                'alternateId':  alternateId if alternateId else line.product_id.default_code,
                'alternateIdType': 'BUYER_ASSIGNED' if alternateId else 'SUPPLIER_ASSIGNED',
                'codigo': line.product_id.l10n_mx_edi_coppel_codigo or '',
                'talla': line.product_id.l10n_mx_edi_coppel_talla or '',
                'descripcion': line.name or '',
                'cantidad': line.quantity,
                'uom': line.uom_id.name,
                'grossPrice': float(grossPrice),
                'netPrice': float(grossPrice),
                'palletQuantity': line_coppel.l10n_mx_edi_coppel_palletqty or 0,
                'palletDescription': line_coppel.l10n_mx_edi_coppel_palletdesc or 'BOX',
                'methodOfPayment': line_coppel.l10n_mx_edi_coppel_palletmethod or 'PREPAID_BY_SELLER',
                'prepactCant': line_coppel.l10n_mx_edi_coppel_palletprepactqty or 0,
                'totalLineAmount': ( float(grossPrice) * line.quantity )
            })
            indx += 1
        documentStatus = 'ORIGINAL'
        if self.l10n_mx_edi_origin:
            documentStatus = 'REEMPLAZA'
        entityType = 'INVOICE '
        if self.type == 'out_refund':
            entityType = 'CREDIT_NOTE'
        uniqueCreatorIdentification = '%s%s'%(Serie, Folio)
        DeliveryDate = str(self.l10n_mx_edi_coppel_deliverydate or '').replace('-', '')
        ReferenceDate = str(self.l10n_mx_edi_coppel_refdate or '').replace('-', '')
        streetAddressOne = '%s %s %s '%( shipTo.street_name, shipTo.street_number, shipTo.l10n_mx_edi_colony  )
        city = '%s'%( shipTo.l10n_mx_edi_locality or shipTo.city_id.name or '' )
        TotalLotes = self.l10n_mx_edi_coppel_totallotes if (self.l10n_mx_edi_coppel_totallotes >= 1) else lenTotalLotes
        cadena = self._get_l10n_mx_edi_cadena()
        res = {
            'documentStatus': documentStatus,
            'DeliveryDate': DeliveryDate or '',
            'entityType': entityType,
            'uniqueCreatorIdentification': uniqueCreatorIdentification[:17],
            'referenceIdentification': self.l10n_mx_edi_coppel_refid or '',
            'ReferenceDate': ReferenceDate or '',

            'gln': company_id.l10n_mx_edi_coppel_gln or '',
            'alternatePartyIdentification': company_id.l10n_mx_edi_coppel_alternateid or '',
            'IndentificaTipoProv': company_id.l10n_mx_edi_coppel_tipoprov or '2',

            'shipto_gln': shipTo.l10n_mx_edi_coppel_gln or '',
            'shipto_name': (shipTo.name or '')[:35],
            'streetAddressOne': streetAddressOne[:35],
            'city': city,
            'postalCode': shipTo.zip,
            'bodegaEnt': shipTo.l10n_mx_edi_coppel_bodegaent or '',

            'currencyISOCode': Moneda or 'MXN',
            'rateOfChange': TipoCambio,
            'TotalLotes': TotalLotes,
            'Conceptos': Conceptos,
            'totalAmount': Total or 0.0,
            'baseAmount': SubTotal or 0.0,
            'taxAmount': TotalImpuestosTrasladados or 0.0,
            'Cadena': cadena
        }
        _logger.info('------addenda_params:\n%s', pprint.pformat(res))
        return res

    @api.multi
    def action_test_addenda(self):
        self.ensure_one()
        addenda = self.partner_id.l10n_mx_edi_addenda
        if addenda:
            values = {
                'record': self,
            }
            add_str = addenda.render(values=values)
            print('-------- add_str', add_str)
            raise UserError(add_str)
        else:
            raise UserError("No existe addenda relacionada")
        return True