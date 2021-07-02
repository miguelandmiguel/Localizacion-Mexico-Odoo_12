# -*- coding: utf-8 -*-

import base64
import logging
import requests
import pprint

from lxml import etree, objectify
from lxml.objectify import fromstring

from werkzeug import url_quote
from os.path import join
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo import api, fields, models, tools, SUPERUSER_ID

_logger = logging.getLogger(__name__)

BODEGAMUEBLES = [
    (30001, '[30001] CULIACAN'),
    (30002, '[30002] LEON'),
    (30003, '[30003] HERMOSILLO'),
    (30004, '[30004] LAGUNA'),
    (30006, '[30006] MONTERREY'),
    (30007, '[30007] GUADALAJARA'),
    (30008, '[30008] AZCAPOTZALCO'),
    (30009, '[30009] PUEBLA'),
    (30010, '[30010] VILLA HERMOSA'),
    (30011, '[30011] IZTAPALAPA'),
    (30012, '[30012] IMP_MXL2'),
    (30013, '[30013] MEXICALI'),
    (30014, '[30014] IZCALLI'),
    (30015, '[30015] IXTAPALUCA'),
    (30016, '[30016] TECAMAC'),
    (30017, '[30017] MERIDA'),
    (30018, '[30018] LOS MOCHIS'),
    (30019, '[30019] VERACRUZ'),
    (30020, '[30020] GUADALAJARA II '),
    (30021, '[30021] IXTAPALUCA IMP'),
    (30022, '[30022] TOLUCA'),
    (30030, '[30030] TECAMAC II'),
    (30031, '[30031] PUEBLA II'),
]

REGIONCEL = [
    (1, 'La Paz, Tijuana, Mexicali'),
    (2, 'Culiacán, Hermosillo, Los Mochis.'),
    (3, 'Laguna.'),
    (4, 'Monterrey.'),
    (5, 'Guadalajara.'),
    (6, 'León, Izcalli.'),
    (7, 'Puebla.'),
    (8, 'Villahermosa, Merida.'),
    (9, 'México, Iztapalapa, Izcalli, Ixtapaluca, Tecamac.'),
]


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
    
    l10n_mx_edi_coppel_compmaterial = fields.Char(string='Material ')
    l10n_mx_edi_coppel_compgrmrelleno = fields.Float(string='Gramaje ')
    l10n_mx_edi_coppel_compgrmrellenoudm = fields.Char(string='U. de Medida ')
    l10n_mx_edi_coppel_compkilataje = fields.Float(string='Kilataje ')
    l10n_mx_edi_coppel_comppeso = fields.Float(string='Peso ')
    l10n_mx_edi_coppel_comppesoudm = fields.Char(string='Peso UdM')

    l10n_mx_edi_coppel_proddate = fields.Char(string='Fecha de Produccion ')
    l10n_mx_edi_coppel_nolote = fields.Char(string='No Lote ')
    l10n_mx_edi_coppel_modelo = fields.Char(string='Modelo ')
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
        addenda_coppel = self.env.ref('l10n_mx_addenda.l10n_mx_edi_addenda_coppel_muebles', raise_if_not_found=False)
        addenda = (self.partner_id.l10n_mx_edi_addenda or self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        self.l10n_mx_edi_inv_addenda = True if addenda.id == addenda_coppel.id else False

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

    l10n_mx_edi_coppel_bodegadest = fields.Selection(BODEGAMUEBLES, string='Bodega Destino')
    l10n_mx_edi_coppel_bodegarecep = fields.Selection(BODEGAMUEBLES, string='Bodega Receptora')
    l10n_mx_edi_coppel_fechapromesaent = fields.Date(string='Fecha Promesa Entrega ')
    l10n_mx_edi_coppel_fleteCaja = fields.Char(string='Flete Caja ')
    l10n_mx_edi_coppel_allowancecharge = fields.Selection([
            ('ALLOWANCE_GLOBAL', 'Descuento Global'),
            ('CHARGE_GLOBAL', 'Cargo Global')
        ], string='Cargo / Descuento', default='ALLOWANCE_GLOBAL')
    l10n_mx_edi_coppel_allowancechargetype = fields.Selection([
            ('BILL_BACK', '[BILL_BACK] Reclamacion'),
            ('OFF_INVOICE', '[OFF_INVOICE] Fuera de Factura')
        ], string='Tipo Cargo / Descuento', default='BILL_BACK')
    l10n_mx_edi_coppel_allowancechargeservice = fields.Selection([
            ('AA', '[AA] Abono por Publicidad'),
            ('EAB', '[EAB] Descuento por pronto pago'),
            ('DXDIST', '[DXDIST] Descuento por distribuir la mercancia de bodega a tienda.'),
            ('DXALM', '[DXALM] Descuento por resguardar la mercancia'),
            ('DXECEN', '[DXECEN] Descuento por entregar en una sola bodega'),
        ], string='Tipo Cargo / Descuento', default='EAB')

    l10n_mx_edi_coppel_type = fields.Selection([
            ('1', 'Mueble'),
            ('2', 'Ropa')
        ], string="Tipo Proveedor", default='1')
    l10n_mx_edi_coppel_regioncel = fields.Selection(REGIONCEL, string="Region Celular")
    l10n_mx_edi_coppel_nopedimento = fields.Char(string='Numero de Pedimento ')

    l10n_mx_edi_coppel_cotizaoro = fields.Float(string='Cotizacion del Oro.', help="Solo Facturacion de Joyerias")
    l10n_mx_edi_coppel_totalpeso = fields.Float(string='Total Peso.', help="Indica el peso total en gramos de las lineas de articulo. Solo Facturacion de Joyerias")
    l10n_mx_edi_coppel_totalpesoudm = fields.Float(string='Total Peso UdM.', help="Indica el peso total en gramos de las lineas de articulo. Solo Facturacion de Joyerias")

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
        Descuento = cfdi.get('Descuento', 0.0) if cfdi is not None else None
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
                'descripcion': line.name[:35] or '',
                'cantidad': line.quantity,
                'uom': (line.uom_id.name or '').replace('(', '').replace(')', '').replace('/', ''),
                'grossPrice': float(grossPrice),
                'netPrice': float(grossPrice),
                'palletQuantity': line_coppel.l10n_mx_edi_coppel_palletqty or 0,
                'palletDescription': line_coppel.l10n_mx_edi_coppel_palletdesc or 'BOX',
                'methodOfPayment': line_coppel.l10n_mx_edi_coppel_palletmethod or 'PREPAID_BY_SELLER',
                'prepactCant': line_coppel.l10n_mx_edi_coppel_palletprepactqty or 0,
                'modelo': line_coppel.l10n_mx_edi_coppel_modelo or False,
                'lotnumber': line_coppel.l10n_mx_edi_coppel_nolote or False,
                'productionDate': line_coppel.l10n_mx_edi_coppel_proddate or False,
                'totalLineAmount': ( float(grossPrice) * line.quantity ),

                'compMaterial': line_coppel.l10n_mx_edi_coppel_compmaterial or False,
                'compGrmRelleno': line_coppel.l10n_mx_edi_coppel_compgrmrelleno or False,
                'compGrmRellenoUdM': line_coppel.l10n_mx_edi_coppel_compgrmrellenoudm or False,
                'compKilataje': line_coppel.l10n_mx_edi_coppel_compkilataje or False,
                'compPeso': line_coppel.l10n_mx_edi_coppel_comppeso or False,
                'compPesoUdM': line_coppel.l10n_mx_edi_coppel_comppesoudm or False,
            })
            indx += 1
        documentStatus = 'ORIGINAL'
        if self.l10n_mx_edi_origin:
            documentStatus = 'REEMPLAZA'
        entityType = 'INVOICE '
        if self.type == 'out_refund':
            entityType = 'CREDIT_NOTE'
        uniqueCreatorIdentification = '%s%s'%(Serie, Folio)
        
        
        streetAddressOne = '%s %s %s '%( shipTo.street_name, shipTo.street_number, shipTo.l10n_mx_edi_colony  )
        city = '%s'%( shipTo.l10n_mx_edi_locality or shipTo.city_id.name or '' )
        TotalLotes = self.l10n_mx_edi_coppel_totallotes if (self.l10n_mx_edi_coppel_totallotes >= 1) else lenTotalLotes
        cadena = self._get_l10n_mx_edi_cadena()

        DeliveryDate = str(self.l10n_mx_edi_coppel_deliverydate or '').replace('-', '')
        # DeliveryDate = self.l10n_mx_edi_coppel_deliverydate or ''

        FechaPromesaEnt = self.l10n_mx_edi_coppel_fechapromesaent
        ReferenceDate = self.l10n_mx_edi_coppel_refdate
        if self.l10n_mx_edi_coppel_type == '2':
            ReferenceDate = str(self.l10n_mx_edi_coppel_refdate or '').replace('-', '')

        res = {
            'adendaType': self.l10n_mx_edi_coppel_type,
            'documentStatus': documentStatus,
            'DeliveryDate': DeliveryDate or '',
            'entityType': entityType,
            'uniqueCreatorIdentification': uniqueCreatorIdentification[:17],
            'referenceIdentification': self.l10n_mx_edi_coppel_refid or '',
            'ReferenceDate': ReferenceDate or '',
            'FechaPromesaEnt': FechaPromesaEnt,

            'gln': company_id.l10n_mx_edi_coppel_gln or '',
            'alternatePartyIdentification': company_id.l10n_mx_edi_coppel_alternateid or '',
            'IndentificaTipoProv': self.l10n_mx_edi_coppel_type or company_id.l10n_mx_edi_coppel_tipoprov or '2',

            'shipto_gln': shipTo.l10n_mx_edi_coppel_gln or '',
            'shipto_name': (shipTo.name or '')[:35],
            'streetAddressOne': streetAddressOne[:35],
            'city': city,
            'postalCode': shipTo.zip,
            'bodegaEnt': shipTo.l10n_mx_edi_coppel_bodegaent or '',
            'bodegaDestino': self.l10n_mx_edi_coppel_bodegadest or False,
            'bodegaReceptora': self.l10n_mx_edi_coppel_bodegarecep or False,
            'RegionCel': self.l10n_mx_edi_coppel_regioncel or False,
            'noPedimento': self.l10n_mx_edi_coppel_nopedimento or False,
            'cotizaOro': self.l10n_mx_edi_coppel_cotizaoro or False,
            'totalPeso': self.l10n_mx_edi_coppel_totalpeso or False,
            'totalPesoUdM': self.l10n_mx_edi_coppel_totalpesoudm or False,

            'fleteCaja': self.l10n_mx_edi_coppel_fleteCaja or False,
            'allowanceChargeType': self.l10n_mx_edi_coppel_allowancecharge or 'ALLOWANCE_GLOBAL',
            'settlementType': self.l10n_mx_edi_coppel_allowancechargetype or 'BILL_BACK',
            'specialServicesType': self.l10n_mx_edi_coppel_allowancechargeservice or 'EAB',

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
            raise UserError(add_str)
        else:
            raise UserError("No existe addenda relacionada")
        return True

    @api.multi
    def action_generate_addendacoppel(self):
        self.ensure_one()
        if not self.action_generate_addendacoppel:
            return True
        addenda = self.env.ref('l10n_mx_addenda.l10n_mx_edi_addenda_coppel_muebles', raise_if_not_found=False)
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