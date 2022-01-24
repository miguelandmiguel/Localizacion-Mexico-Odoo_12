# -*- coding: utf-8 -*-

import base64
import re
import os
from os.path import exists
import logging
import requests
import pprint
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from xml.dom.minidom import parse, parseString
from lxml import etree as ETX
from lxml import etree
from lxml.objectify import fromstring
from datetime import datetime, timedelta
from functools import partial
from itertools import groupby
from suds.client import Client
from suds.plugin import MessagePlugin

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit
from odoo import api, fields, models, SUPERUSER_ID, _, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT

import odoo.modules as addons
from odoo.tools import config

from werkzeug.urls import url_encode

logging.basicConfig(level=logging.INFO)
logging.getLogger('suds.client').setLevel(logging.DEBUG)


NS = "cfdi:"
NSCP = "cartaporte20:"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"

class LogPlugin(MessagePlugin):
    def pretty_log(self, xml_content):
        try:
            tree = fromstring( '%s'%xml_content )
            xml = etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
            logging.info( '%s'%xml )
        except:
            logging.info( '%s'%xml_content)

    def sending(self, context):
        self.pretty_log( '%s'%context.envelope )
    def received(self, context):
        self.pretty_log( '%s'%context.reply)

CFDI_TEMPLATE_33 = 'cfd_mx_traslado.cfdiv33'
CFDI_XSLT_CADENA = 'cfd_mx_traslado/data/%s/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'cfd_mx_traslado/data/xslt/3.3/cadenaoriginal_TFD_1_1.xslt'
CFDI_XSLT_CADENA_TRASL = 'cfd_mx_traslado/data/%s/CartaPorte20.xslt'


def create_list_html(array):
    '''Convert an array of string to a html list.
    :param array: A list of strings
    :return: an empty string if not array, an html list otherwise.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class StockPicking(models.Model):
    _inherit = "stock.picking"

    cfditraslado_id = fields.Many2one('cfdi.traslados', string='CFDI Reference', required=False, ondelete='cascade', index=True, copy=False)

class StockMove(models.Model):
    _inherit = "stock.move"

    cfditraslado_id = fields.Many2one('cfdi.traslados', string='CFDI Reference', required=False, ondelete='cascade', index=True, copy=False)

# cfdi_traslado_stock_picking
class CfdiTrasladoStockPicking(models.TransientModel):
    _name="cfdi.traslado.stock.picking"

    name = fields.Char(string='Agregar Remisiones', readonly="1")
    picking_ids = fields.Many2many('stock.picking', string='Picking Lines', 
        domain=[('state','=','done'), ('move_lines', '!=', False), ('cfditraslado_id', '=', False)], 
        help="Preferred route to be followed by the order")


    def acction_picking(self):
        ctx = dict(self._context or {})
        traslado_id = self.env[ ctx.get('active_model') ].browse( ctx.get('active_id') )
        # 'cfdi_line_ids': [(4,  move_ids)]
        for rec in self:
            for pick in rec.picking_ids:
                traslado_id.write({
                    'picking_ids': [(4, pick.id)], 
                })


# Modelos
# cfdi_traslados
class CfdiTraslados(models.Model):
    _name = 'cfdi.traslados'
    _inherit = ['mail.thread']
    _inherits = {'cfdi.cartaporte': 'cartaporte_id'}
    _description="CFDI de Traslados"

    @api.model
    def _default_partner_id(self):
        return self.env.user.company_id.partner_id or False

    cartaporte_id = fields.Many2one('cfdi.cartaporte', required=True, ondelete='restrict', auto_join=True,
        string='Related CartaPorte', help='CartaPorte-related data of the user')    

    name = fields.Char(
        string='Reference', required=True, copy=False, 
        readonly=True, states={'draft': [('readonly', False)]}, 
        index=True, default=lambda self: _('New'))
    origin = fields.Char(string='Source Document',
        help="Reference of the document that produced this invoice.",
        readonly=True, states={'draft': [('readonly', False)]})
    type = fields.Selection([
            ('out','Customer Invoice'),
            ('in','Vendor Bill'),
            ('internal','Customer Refund'),
        ], readonly=True, index=True, change_default=True,
        default=lambda self: self._context.get('type', 'in'),
        track_visibility='always')
    date_invoice = fields.Date(string='Invoice Date',
        readonly=False, states={'draft': [('readonly', False)]}, index=True,
        help="Keep empty to use the current date", copy=False)
    confirmation_date = fields.Datetime(
        string='Confirmation Date', required=True, 
        readonly=True, index=True, 
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False, default=fields.Datetime.now, 
        help="Creation date of draft/sent orders,\nConfirmation date of confirmed orders.")
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('cfdi.traslados'))
    state = fields.Selection([
            ('draft','Draft'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False,
        help=" * The 'Draft' status is used when a user is encoding a new and unconfirmed Invoice.\n"
             " * The 'Pro-forma' status is used when the invoice does not have an invoice number.\n"
             " * The 'Open' status is used when user creates invoice, an invoice number is generated. It stays in the open status till the user pays the invoice.\n"
             " * The 'Paid' status is set automatically when the invoice is paid. Its related journal entries may or may not be reconciled.\n"
             " * The 'Cancelled' status is used when user cancel invoice.")

    cfdi_require_cartaporte = fields.Boolean("Requiere CartaPorte")

    # cfdi_line_ids = fields.One2many('stock.move', 'cfditraslado_id', string='Stock Move Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)
    picking_ids = fields.Many2many(
        'stock.picking', 'stock_picking_cfdi_traslado', 
        'picking_id', 'cfdi_id', 'Picking Lines', 
        domain=[('state','=','done')], 
        help="Preferred route to be followed by the order")

    cfdi_line_ids = fields.Many2many(
        'stock.move', 'stock_move_cfdi_traslado', 
        'move_id', 'cfdi_id', 'Stock Move Lines', 
        domain=[('picking_id.state','=','done'), ('state', '=', 'done')], 
        help="Preferred route to be followed by the order")

    partner_id = fields.Many2one('res.partner', string='Partner', change_default=True,
        required=True, readonly=False, track_visibility='always',
        default=_default_partner_id)

    # CFDI
    cfdi_timbre_id = fields.Many2one('cfdi.timbres.sat', string=u'Timbre SAT', copy=False)
    cfdi_test = fields.Boolean(string="Timbrado en modo de prueba", copy=False)
    cfdi_uuid = fields.Char(string='Timbre fiscal', copy=False)

    l10n_mx_edi_time_invoice = fields.Char(
        string='Time invoice', readonly=False, copy=False,
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the current México central time")
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origin', copy=False,
        help='In some cases like payments, credit notes, debit notes, '
        'invoices re-signed or invoices that are redone due to payment in '
        'advance will need this field filled, the format is: \nOrigin Type|'
        'UUID1, UUID2, ...., UUIDn.\nWhere the origin type could be:\n'
        u'- 01: Nota de crédito\n'
        u'- 02: Nota de débito de los documentos relacionados\n'
        u'- 03: Devolución de mercancía sobre facturas o traslados previos\n'
        u'- 04: Sustitución de los CFDI previos\n'
        '- 05: Traslados de mercancias facturados previamente\n'
        '- 06: Factura generada por los traslados previos\n'
        u'- 07: CFDI por aplicación de anticipo')

    cfdi_reason_cancel = fields.Selection(
        selection=[
            ('01', u'[01] Comprobante Emitido con errores con relación'),
            ('02', u'[02] Comprobante Emitido con errores sin relación'),
            ('03', u'[03] No se llevo a cabo la operación'),
            ('04', u'[04] Operación nominativa relacionada en una factura global'),
        ],        
        string="CFDI Reason Cancel", copy=False)
    uuid_relacionado_id = fields.Many2one('cfdi.traslados', string=u'UUID Relacionado', domain=[("cfdi_uuid", "!=", None), ("state", "=", 'done')])
    uuid_egreso = fields.Char('UUID Relacionado')


    # CFDI Carta Porte
    @api.model
    def create(self, vals):
        result = super(CfdiTraslados, self).create(vals)
        return result

    @api.multi
    def write(self, vals):
        ctx = dict(self._context)
        if not 'cfdi_picking' in ctx:
            for inv in self:
                inv.picking_ids.write({'cfditraslado_id': None})
        res = super(CfdiTraslados, self).write(vals)
        if 'picking_ids' in vals:
            m_ids = []
            for inv in self.with_context(cfdi_picking=True):
                inv.picking_ids.write({'cfditraslado_id': inv.id})
                for p_id in inv.picking_ids:
                    m_ids.extend(p_id.move_lines.ids)
                inv.write({'cfdi_line_ids': [(6, 0, m_ids)]})
        return res

    @api.onchange('cfdi_transporte_id')
    def onchange_cfdi_transporte_id(self):
        transpDatas = {
            'cfdi_autotransporte_permsct_id': None, 'cfdi_autotransporte_numpermisosct': None, 'cfdi_autotransporte_configvehicular_id': None, 
            'cfdi_autotransporte_placavm': None, 'cfdi_autotransporte_aniomodelovm': None, 'cfdi_autotransporte_nombreaseg': None,
            'cfdi_autotransporte_polizaeaseg': None, 'cfdi_autotransporte_aseguramedambiente': None, 'cfdi_autotransporte_polizamedambiente': None,
            'cfdi_autotransporte_aseguracarga': None, 'cfdi_autotransporte_polizacarga': None, 'cfdi_autotransporte_primaseguro': None,
            'cfdi_autotransporte_subtiporem_id': None, 'cfdi_autotransporte_placa': None, 'cfdi_autotransporte_subtiporem02_id': None,
            'cfdi_autotransporte_placa02': None
        }
        if self.cfdi_transporte_id:
            transpDatasTmp = transpDatas.copy()
            for transpId in self.env['cfdi.cartaporte.transporte'].search_read([('id', '=', self.cfdi_transporte_id.id)], transpDatas.keys()):
                transpId.pop('id')
                transpDatas = transpId
        self.update(transpDatas)


    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        self.ensure_one()
        if not self.cfdi_uuid:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', '%s.xml'%self.cfdi_uuid)]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids and attachment_ids[0] or None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        self.ensure_one()
        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        if cfdi is None and attachment_id:
            datas = attachment_id._file_read(attachment_id.store_fname)
            cfdi = base64.decodestring(datas)
        return fromstring(cfdi) if cfdi else None

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.multi
    def _compute_cfdi_values(self):
        for inv in self:
            attachment_id = inv.l10n_mx_edi_retrieve_last_attachment()
            datas = attachment_id._file_read(attachment_id.store_fname)
            if not attachment_id:
                continue
            tree = inv.l10n_mx_edi_get_xml_etree()
            tfd_node = inv.l10n_mx_edi_get_tfd_etree(tree)
            cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % '3.3', tree)
            vals = {
                'UUID': tfd_node.get('UUID'),
                'SelloCFD': tfd_node.get('SelloCFD'),
                'SelloSAT': tfd_node.get('SelloSAT'),
                'NoCertificadoSAT': tfd_node.get('NoCertificadoSAT'),
                'Version': tree.get('Version', tree.get('version')),
                'Total': float(tree.get('Total', tree.get('total'))),
                'RfcEmisor': tree.Emisor.get('Rfc', tree.Emisor.get('rfc')),
                'RfcReceptor': tree.Receptor.get('Rfc', tree.Receptor.get('rfc')),
                'noCertificado': tree.get('noCertificado', tree.get('NoCertificado')),
                'cadenaOriginal': cadena,
                'cadenaSat': ""
            }
            return vals        

    


    def action_cfdi_open(self):
        for inv in self:
            if inv.cfdi_uuid:
                continue

            service_type = 'sign'
            pac_name = inv.company_id.l10n_mx_edi_pac
            pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
            pac_info = getattr(self, pac_info_func)(inv.company_id, service_type)

            certificate_id = self._get_certificate()
            xml = self.action_cfdi_open_xml()
            cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % '3.3', fromstring(xml))
            node_sello = certificate_id.sudo().get_encrypted_cadena(cadena)
            xml = xml.replace(b'Sello=""', b'Sello="%s"'%(node_sello) )

            url = pac_info['url']
            username = pac_info['username']
            password = pac_info['password']
            logging.info('--- XML %s - Username  %s %s '%(xml, username, password) )
            extra = False
            cfdi = base64.encodestring(xml).decode('UTF-8')
            response = None
            try:
                client = Client(url, cache=None, timeout=80)
                response = client.service.stamp(cfdi, username, password)
                logging.info('-- _traslado_cfdi-reques: Values received:\n%s', pprint.pformat(response))
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                return {'error': str(e)}
                continue
            code = 0
            msg = None
            xml_signed = getattr(response, 'xml', None)
            if response.Incidencias:
                code = getattr(response.Incidencias[0][0], 'CodigoError', None)
                msg = getattr(response.Incidencias[0][0], 'MensajeIncidencia', None)
                extra = getattr(response.Incidencias[0][0], 'ExtraInfo', None)
                if extra:
                    msg += '  %s'%extra
                xml_signed = base64.b64encode((xml_signed or '').encode('utf-8'))
                inv._l10n_mx_edi_post_sign_process(xml_signed, code, msg, {})
                body_msg = _('The sign service requested failed')
                inv.message_post(
                    body=body_msg + create_list_html([msg]))
                return {
                    'error': msg
                }
            res = {}
            if xml_signed:
                res = {
                    'UUID': getattr(response, 'UUID', '')
                }                
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            inv._l10n_mx_edi_post_sign_process(xml_signed, code, msg, res)
            return res


    @api.multi
    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None, res={}):
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.pop('default_type', False)
        version = self.l10n_mx_edi_get_pac_version()
        if xml_signed:
            body_msg = _('The sign service has been called with success')
            # self.l10n_mx_edi_pac_status = 'signed'
            # self.l10n_mx_edi_cfdi = xml_signed
            xname = "%s.xml"%res.get('UUID', '')
            attachment_values = {
                'name':  xname,
                'datas': xml_signed,
                'datas_fname': xname,
                'description': 'Comprobante Fiscal Digital',
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/xml'
            }
            self.env['ir.attachment'].create(attachment_values)
            self.write({
                'state': 'done',
                'cfdi_uuid': res.get('UUID', ''),
                'cfdi_test': self.company_id.l10n_mx_edi_pac_test_env
            })
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg))

    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        '''Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information contained within the cfdi.
        This can be encoded with the certificate to create the digital seal.
        Since the cadena is generated with the invoice data, any change in it will be noticed resulting in a different
        cadena and so, ensure the invoice has not been modified.

        :param xslt_path: The path to the xslt file.
        :param cfdi_as_tree: The cfdi converted as a tree
        :return: A string computed with the invoice data called the cadena
        '''
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.multi
    def _l10n_mx_edi_finkok_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        if service_type == 'sign':
            url = 'http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/stamp.wsdl'
        else:
            url = 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'cfdi@vauxoo.com' if test else username,
            'password': 'vAux00__' if test else password,
        }

    @api.multi
    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message)

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        version = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_cfdi_version', '3.3')
        return version        


    # Obtiene datos para las mercancias
    def getDatasCartaPorteMercancias(self):
        seq = 10
        MercaModel = self.env['cfdi.cartaporte.mercancias']
        for line in self.cfdi_line_ids:
            vals = {
                'name': line.product_id.name,
                'sequence': seq,
                'cartaporte_id': self.cartaporte_id.id,
                'bienestransp_id': line.product_id.l10n_mx_edi_code_sat_id.id or 'False',
                'descripcion': line.name,
                'cantidad': line.product_uom_qty,
                'unidad': line.product_uom and line.product_uom.name or '',
                'claveunidad_id': line.product_uom.l10n_mx_edi_code_sat_id.id or None,
                'product_id': line.product_id.id,
                'stock_id': line.id
            }
            seq += 1
            merca_id = MercaModel.search([('cartaporte_id', '=', self.cartaporte_id.id), ('stock_id', '=', line.id)])
            if merca_id:
                merca_id.write(vals)
            else:
                MercaModel.create(vals)
        return {}


    """
    -- 
    -- 
    -- 
    """
    @staticmethod
    def _get_string_cfdi(text, size=100):
        """Replace from text received the characters that are not found in the
        regex. This regex is taken from SAT documentation
        https://goo.gl/C9sKH6
        text: Text to remove extra characters
        size: Cut the string in size len
        Ex. 'Product ABC (small size)' - 'Product ABC small size'"""
        if not text:
            return None
        text = text.replace('|', ' ')
        return text.strip()[:size]

    @staticmethod
    def _l10n_mx_get_serie_and_folio(number):
        values = {'serie': None, 'folio': None}
        number = (number or '').strip()
        number_matchs = [rn for rn in re.finditer('\d+', number)]
        if number_matchs:
            last_number_match = number_matchs[-1]
            values['serie'] = number[:last_number_match.start()] or None
            values['folio'] = last_number_match.group().lstrip('0') or None
        return values

    @api.multi
    def get_mx_current_datetime(self):
        '''Get the current datetime with the Mexican timezone.
        '''
        timenow = fields.Datetime.now()
        timenow = datetime.strptime('%s'%timenow, '%Y-%m-%d %H:%M:%S')
        return fields.Datetime.context_timestamp(
            self.with_context(tz='America/Mexico_City'), timenow)

    @api.multi
    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if not self.uuid_relacionado_id:
            return {}
        return {
            'type': '04',
            'related': self.uuid_relacionado_id and self.uuid_relacionado_id.cfdi_uuid
        }

    @api.multi
    def _l10n_mx_edi_create_cfdi_values(self):
        '''Create the values to fill the CFDI template.'''
        self.ensure_one()
        values = {
            'record': self,
            'currency_name': 'MXN',
        }
        values.update(self._l10n_mx_get_serie_and_folio(self.name))
        return values

    @api.multi
    def _l10n_mx_edi_create_cfdi(self):
        self.ensure_one()
        
        error_log = []
        company_id = self.company_id
        values = self._l10n_mx_edi_create_cfdi_values()

        # -Compute date and time of the invoice
        time_invoice = datetime.strptime(self.l10n_mx_edi_time_invoice, DEFAULT_SERVER_TIME_FORMAT).time()
        # -Compute certificate data
        values['date'] = datetime.combine(fields.Datetime.from_string(self.date_invoice), time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
        return values

    def _get_certificate(self):
        certificate_ids = self.company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        return certificate_id

    def get_comprobante(self, values={}):
        certificate_id = self._get_certificate()
        certificate = certificate_id.sudo().get_data()[0]
        comprobante_attribs = {
            'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/3',
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xsi:schemaLocation': 'http://www.sat.gob.mx/cfd/3 http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd',
            'Version': '3.3',
            'Fecha': values['date'],
            'Folio': self._get_string_cfdi(values['folio'] or '', 40),
            'Serie': self._get_string_cfdi(values['serie'] or '', 40),
            'Sello': '',
            'NoCertificado': "%s"%(certificate_id.serial_number or ''),
            'Certificado': certificate.decode('utf-8'),
            'SubTotal': "0" if self.cfdi_require_cartaporte else '0.0' ,
            'Moneda': 'XXX' if self.cfdi_require_cartaporte else 'MXN',
            'Total': "0" if self.cfdi_require_cartaporte else '0.0' ,
            'TipoDeComprobante': 'T',
            'LugarExpedicion': self.partner_id and self.partner_id.zip or ''
        }
        if self.cfdi_require_cartaporte:
            comprobante_attribs['xsi:schemaLocation'] = comprobante_attribs['xsi:schemaLocation'] + ' http://www.sat.gob.mx/CartaPorte20 http://www.sat.gob.mx/sitio_internet/cfd/CartaPorte/CartaPorte20.xsd'
        if not self.cfdi_require_cartaporte:
            comprobante_attribs['TipoCambio'] = '1'
        return comprobante_attribs

    def get_relacionados(self, comprobante=None):
        related = self.get_cfdi_related()
        if related:
            nodo_relacionados = ET.SubElement(comprobante, NS+'CfdiRelacionados', {
                'TipoRelacion': related.get('type')
            })
            for number in related.get('related', []):
                nodo_relacionado = ET.SubElement(nodo_relacionados, NS+'CfdiRelacionado', {
                    'UUID': number
                })
        return comprobante

    def get_emisor(self, comprobante=None):
        partner_data = self.partner_id
        fiscal_position = partner_data.property_account_position_id
        emisor_attribs = {
            'Rfc': partner_data.vat or "",
            'Nombre': partner_data.name or "",
            "RegimenFiscal": fiscal_position.l10n_mx_edi_code or ""
        }
        nodo_emisor = ET.SubElement(comprobante, NS+'Emisor', emisor_attribs)
        return comprobante

    def get_receptor(self, comprobante=None):
        receptor_attribs = {
            'Rfc': self.partner_id.vat if self.cfdi_require_cartaporte else 'XAXX010101000',
            'Nombre': self.partner_id.name,
            'UsoCFDI': 'P01',
        }
        nodo_receptor = ET.SubElement(comprobante, NS+'Receptor', receptor_attribs)
        return comprobante

    def get_conceptos(self, comprobante=None):
        if self.cfdi_line_ids:
            nodo_conceptos = ET.SubElement(comprobante, NS+'Conceptos', {})
            for line in self.cfdi_line_ids:
                prod_id = line.product_id
                concepto_attribs = {
                    'ClaveProdServ': line.product_id.l10n_mx_edi_code_sat_id.code or '01010101',
                    'NoIdentificacion': line.product_id and line.product_id.default_code or '',
                    'Cantidad': '%.*f' % (6, line.product_uom_qty),
                    'ClaveUnidad': line.product_uom.l10n_mx_edi_code_sat_id.code or 'H87',
                    'Unidad': line.product_uom and line.product_uom.name or '',
                    'Descripcion': line.name.replace('[', '').replace(']', '') or '',
                    'ValorUnitario': '0.0',
                    'Importe': '0.0'
                }
                nodo_concepto = ET.SubElement(nodo_conceptos, NS+'Concepto', concepto_attribs)
        return comprobante

    def get_cartaporte(self, comprobante=None):
        if self.cfdi_require_cartaporte:
            nodo_complemento = ET.SubElement(comprobante, 'cfdi:Complemento', {})

            cartaporte_attribs = {
                'Version': '2.0',
                'xmlns:cartaporte20': "http://www.sat.gob.mx/CartaPorte20"
            }
            if self.cfdi_cartaporte_transpinter:
                cartaporte_attribs['TranspInternac'] = self.cfdi_cartaporte_transpinter
            if self.cfdi_cartaporte_transpinter != 'No':
                if self.cfdi_cartaporte_entradasalidamerc:
                    cartaporte_attribs['EntradaSalidaMerc'] = self.cfdi_cartaporte_entradasalidamerc
                if self.cfdi_cartaporte_paisorgdest_id:
                    cartaporte_attribs['PaisOrigenDestino'] = self.cfdi_cartaporte_paisorgdest_id and self.cfdi_cartaporte_paisorgdest_id.l10n_mx_edi_code or ''
                if self.cfdi_clavetransporte_id:
                    cartaporte_attribs['ViaEntradaSalida'] = self.cfdi_clavetransporte_id and self.cfdi_clavetransporte_id.clave or ''
            if self.cfdi_cartaporte_totaldistrec:
                cartaporte_attribs['TotalDistRec'] = "%s"%self.cfdi_cartaporte_totaldistrec

            nodo_cartaporte = ET.SubElement(nodo_complemento, NSCP+'CartaPorte', cartaporte_attribs)
            # Ubicaciones
            if len(self.cfdi_ubicaciones_ids):
                nodo_ubicaciones = ET.SubElement(nodo_cartaporte, NSCP+'Ubicaciones', {})
                for ubic in self.cfdi_ubicaciones_ids:
                    fechahorasaalida = '%s'%ubic.fechahorasaalida
                    ubic_attribs = {
                        'TipoUbicacion': ubic.tipoubicacion or '',
                        'FechaHoraSalidaLlegada': fechahorasaalida.replace(' ', 'T')
                    }
                    if ubic.ubicacion_id:
                        ubic_attribs['IDUbicacion'] = ubic.ubicacion_id or ''
                    if ubic.remitentedest_id:
                        ubic_attribs['RFCRemitenteDestinatario'] = ubic.remitentedest_id.vat or ''
                        ubic_attribs['NombreRemitenteDestinatario'] = ubic.remitentedest_id.name or ''
                        if ubic.remitentedest_id.country_id and ubic.remitentedest_id.country_id.code != 'MX':
                            ubic_attribs['NumRegIdTrib'] = ubic.remitentedest_id.vat or ''
                            ubic_attribs['ResidenciaFiscal'] = ubic.remitentedest_id.country_id.l10n_mx_edi_code or ''
                    if ubic.numestacion_id:
                        ubic_attribs['NumEstacion'] = ubic.numestacion_id.clave or ''
                        ubic_attribs['NombreEstacion'] = ubic.numestacion_id.name or ''
                    if ubic.navegaciontrafico:
                        ubic_attribs['NavegacionTrafico'] = ubic.navegaciontrafico or ''
                    if ubic.tipoestacion_id:
                        ubic_attribs['TipoEstacion'] = ubic.tipoestacion_id and ubic.tipoestacion_id.clave or ''
                    if ubic.distanciarecorrida:
                        ubic_attribs['DistanciaRecorrida'] = '%s'%ubic.distanciarecorrida
                    nodo_ubicacion = ET.SubElement(nodo_ubicaciones, NSCP+'Ubicacion', ubic_attribs)
                    if ubic.remitentedest_id:
                        dom = ubic.remitentedest_id
                        doc_attribs = {}
                        if dom.street:
                            doc_attribs['Calle'] = dom.street or ''
                        if dom.street_number:
                            doc_attribs['NumeroExterior'] = dom.street_number or ''
                        if dom.l10n_mx_edi_colony_code:
                            doc_attribs['Colonia'] = dom.l10n_mx_edi_colony_code or ''
                        if dom.l10n_mx_edi_locality_id:
                            doc_attribs['Localidad'] = dom.l10n_mx_edi_locality_id.code or ''
                        if dom.cartaporte_refubicacion:
                            doc_attribs['Referencia'] = dom.cartaporte_refubicacion
                        # if dom.municipio_id:
                        #     doc_attribs['Municipio'] = dom.municipio_id.clave_sat or ''
                        if dom.state_id:
                            doc_attribs['Estado'] = dom.state_id.code or ''
                        if dom.country_id and dom.country_id.l10n_mx_edi_code:
                            doc_attribs['Pais'] = dom.country_id and dom.country_id.l10n_mx_edi_code or ''
                        if (dom.zip):
                            doc_attribs['CodigoPostal'] = dom.zip or ''
                        dom_ubicacion = ET.SubElement(nodo_ubicacion, NSCP+'Domicilio', doc_attribs)

            if len(self.cfdi_mercancia_ids):
                mercas_attribs = {
                    'PesoBrutoTotal': '%s'%self.cfdi_pesobrutototal,
                    'UnidadPeso': '%s'%self.cfdi_unidadpeso_id and self.cfdi_unidadpeso_id.clave or '',
                    'NumTotalMercancias': '%s'%self.cfdi_numtotalmercancias or 1,
                }
                if self.cfdi_pesonetototal:
                    mercas_attribs['PesoNetoTotal'] = '%s'%self.cfdi_pesonetototal or 0.0
                if self.cfdi_cargotasacion:
                    mercas_attribs['CargoPorTasacion'] = '%s'%self.cfdi_cargotasacions or 0.0
                nodo_mercancias = ET.SubElement(nodo_cartaporte, NSCP+'Mercancias', mercas_attribs)

                for merca in self.cfdi_mercancia_ids:
                    merca_attribs = {
                        'BienesTransp': merca.bienestransp_id and merca.bienestransp_id.code or '',
                        'Descripcion': merca.descripcion or '',
                        'Cantidad': '%s'%(merca.cantidad or 0.000001),
                        'ClaveUnidad': merca.claveunidad_id and merca.claveunidad_id.code or '',
                    }
                    if merca.clavestcc_id:
                        merca_attribs['ClaveSTCC'] = merca.clavestcc_id and merca.clavestcc_id.clave or ''
                    if merca.unidad:
                        merca_attribs['Unidad'] = merca.unidad or ''
                    if merca.dimensiones:
                        merca_attribs['Dimensiones'] = merca.dimensiones or ''
                    if merca.materialpeligroso:
                        merca_attribs['MaterialPeligroso'] = merca.materialpeligroso or ''
                        if merca.cvematerialpeligroso_id:
                            merca_attribs['CveMaterialPeligroso'] = merca.cvematerialpeligroso_id and merca.cvematerialpeligroso_id.clave or ''
                        if merca.embalaje_id:
                            merca_attribs['Embalaje'] = merca.embalaje_id and merca.embalaje_id.clave or ''
                        if merca.descripembalaje:
                            merca_attribs['DescripEmbalaje'] = merca.descripembalaje or ''
                        if merca.valormercancia:
                            merca_attribs['ValorMercancia'] = '%s'%(merca.valormercancia or 0)
                        # Moneda
                        if merca.fraccionarancelaria:
                            merca_attribs['FraccionArancelaria'] = '%s'%(merca.fraccionarancelaria or '')
                        if merca.uuicomercioext:
                            merca_attribs['UUIDComercioExt'] = '%s'%(merca.uuicomercioext or '')
                    if merca.pesoenkg:
                        merca_attribs['PesoEnKg'] = '%s'%(merca.pesoenkg or 0)
                    nodo_mercancia = ET.SubElement(nodo_mercancias, NSCP+'Mercancia', merca_attribs)

                    # Pedimentos
                    for ped in merca.pedimento_ids:
                        nodo_pedimentos = ET.SubElement(nodo_mercancia, NSCP+'Pedimentos', {'Pedimento': ped.name})
                    for guia in merca.guias_ids:
                        nodo_guia = ET.SubElement(nodo_mercancia, NSCP+'GuiasIdentificacion', {
                            'NumeroGuiaIdentificacion': guia.name or '',
                            'DescripGuiaIdentificacion': guia.descripcion or '',
                            'PesoGuiaIdentificacion': guia.pesoguiaidentificacion or '',
                        })
                    for cant in merca.cantidadtransporta_ids:
                        nodo_cantidad = ET.SubElement(nodo_mercancia, NSCP+'CantidadTransporta', {
                            'Cantidad': cant.name or '',
                            'IDOrigen': cant.idorigen or '',
                            'IDDestino': cant.iddestino or '',
                            'CvesTransporte': cant.clavetransporte_id and cant.clavetransporte_id.clave or '',
                        })
                    for det in merca.detalle_ids:
                        nodo_detalle = ET.SubElement(nodo_mercancia, NSCP+'DetalleMercancia', {
                            'UnidadPesoMerc': det.unidadpeso_id and det.unidadpeso_id.clave or '',
                            'PesoBruto': '%s'%(det.pesobruto),
                            'PesoNeto': '%s'%(det.pesoneto),
                            'PesoTara': '%s'%(det.pesotara),
                        })
                        if det.numpiezas:
                            nodo_detalle['NumPiezas'] = '%s'%(det.numpiezas)

                if self.cfdi_cartaporte_tipo == '01':
                    nodo_autotransporte = ET.SubElement(nodo_mercancias, NSCP+'Autotransporte', {
                        'PermSCT': self.cfdi_autotransporte_permsct_id and self.cfdi_autotransporte_permsct_id.clave or '',
                        'NumPermisoSCT': self.cfdi_autotransporte_numpermisosct or ''
                    })

                    nodo_identificacionvehicular = ET.SubElement(nodo_autotransporte, NSCP+'IdentificacionVehicular', {
                        'ConfigVehicular': self.cfdi_autotransporte_configvehicular_id and self.cfdi_autotransporte_configvehicular_id.clave or '',
                        'PlacaVM': self.cfdi_autotransporte_placavm or '',
                        'AnioModeloVM': '%s'%(self.cfdi_autotransporte_aniomodelovm)
                    })

                    # Seguros
                    seguro_attribs = {
                        'AseguraRespCivil': self.cfdi_autotransporte_nombreaseg or '',
                        'PolizaRespCivil': self.cfdi_autotransporte_polizaeaseg or '',
                    }
                    if self.cfdi_autotransporte_aseguramedambiente:
                        seguro_attribs['AseguraMedAmbiente'] = self.cfdi_autotransporte_aseguramedambiente or ''
                    if self.cfdi_autotransporte_polizamedambiente:
                        seguro_attribs['PolizaMedAmbiente'] = self.cfdi_autotransporte_polizamedambiente or ''
                    if self.cfdi_autotransporte_aseguracarga:
                        seguro_attribs['AseguraCarga'] = self.cfdi_autotransporte_polizamedambiente or ''
                    if self.cfdi_autotransporte_polizacarga:
                        seguro_attribs['PolizaCarga'] = self.cfdi_autotransporte_polizacarga or ''
                    if self.cfdi_autotransporte_primaseguro:
                        seguro_attribs['PrimaSeguro'] = '%s'%(self.cfdi_autotransporte_primaseguro or 0.0)
                    nodo_seguros = ET.SubElement(nodo_autotransporte, NSCP+'Seguros', seguro_attribs)

                    # Remolques
                    if self.cfdi_autotransporte_subtiporem_id or self.cfdi_autotransporte_subtiporem02_id:
                        nodo_remolques = ET.SubElement(nodo_autotransporte, NSCP+'Remolques', {})
                        if self.cfdi_autotransporte_subtiporem_id:
                            nodo_remolque = ET.SubElement(nodo_remolques, NSCP+'Remolque', {
                                'SubTipoRem': self.cfdi_autotransporte_subtiporem_id and self.cfdi_autotransporte_subtiporem_id.clave or '',
                                'Placa': self.cfdi_autotransporte_placa or ''
                            })
                        if self.cfdi_autotransporte_subtiporem02_id:
                            nodo_remolque = ET.SubElement(nodo_remolques, NSCP+'Remolque', {
                                'SubTipoRem': self.cfdi_autotransporte_subtiporem02_id and self.cfdi_autotransporte_subtiporem02_id.clave or '',
                                'Placa': self.cfdi_autotransporte_placa02 or ''
                            })

                    # FiguraTransporte
                    nodo_figuratransporte = ET.SubElement(nodo_cartaporte, NSCP+'FiguraTransporte', {})
                    for tipo in self.cfdi_tiposfigura_ids:
                        tiposfigura_attribs = {
                            'TipoFigura': tipo.cfdi_figuratransporte_tipofigura_id and tipo.cfdi_figuratransporte_tipofigura_id.clave or ''
                        }
                        if tipo.cfdi_figuratransporte_figura_id:
                            if tipo.cfdi_figuratransporte_figura_id.vat:
                                tiposfigura_attribs['RFCFigura'] = tipo.cfdi_figuratransporte_figura_id.vat or ''
                            if tipo.cfdi_figuratransporte_figura_id.mum_licencia:
                                tiposfigura_attribs['NumLicencia'] = tipo.cfdi_figuratransporte_figura_id.mum_licencia or ''
                            tiposfigura_attribs['NombreFigura'] = tipo.cfdi_figuratransporte_figura_id.name or ''
                            if tipo.cfdi_figuratransporte_figura_id.country_id.l10n_mx_edi_code != 'MEX':
                                tiposfigura_attribs['NumRegIdTribFigura'] = tipo.cfdi_figuratransporte_figura_id.vat or ''
                                tiposfigura_attribs['ResidenciaFiscalFigura'] = cfdi_figuratransporte_figura_id.country_id.l10n_mx_edi_code or ''
                        nodo_tiposfigura = ET.SubElement(nodo_figuratransporte, NSCP+'TiposFigura', tiposfigura_attribs)
        return comprobante

    def action_cfdi_open_xml(self):
        for inv in self:
            if inv.cfdi_uuid:
                continue
            date_mx = inv.get_mx_current_datetime()
            ctx = dict(self._context, lang=inv.company_id.partner_id.lang)
            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            if not inv.l10n_mx_edi_time_invoice:
                inv.l10n_mx_edi_time_invoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)
            inv.confirmation_date = fields.Datetime.now()
            if inv.name == _('New'):
                inv.name = self.env['ir.sequence'].with_context(force_company=inv.company_id.id, ir_sequence_date=inv.date_invoice).next_by_code('cfdi.traslados') or _('New')

            values = self._l10n_mx_edi_create_cfdi()
            comprobante = ET.Element(NS+'Comprobante', self.get_comprobante(values=values) )
            # Relacionados
            comprobante = self.get_relacionados(comprobante=comprobante)
            comprobante = self.get_emisor(comprobante=comprobante)
            comprobante = self.get_receptor(comprobante=comprobante)
            comprobante = self.get_conceptos(comprobante=comprobante)
            comprobante = self.get_cartaporte(comprobante=comprobante)
            xml = ET.tostring(comprobante, encoding='UTF-8', method='xml')
            return xml



    def action_cfdi_cancel(self):
        for inv in self:
            if not inv.cfdi_reason_cancel:
                raise UserError('Es obligatorio el motivo de cancelacion')
            if not inv.cfdi_uuid:
                continue
            pac_info = self._l10n_mx_edi_finkok_info(inv.company_id, 'cancel')
            url = pac_info['url']
            username = pac_info['username']
            password = pac_info['password']

            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            cer_pem = base64.encodestring(certificate_id.get_pem_cer(certificate_id.content)).decode('UTF-8')
            key_pem = base64.encodestring(certificate_id.get_pem_key(certificate_id.key, certificate_id.password)).decode('UTF-8')
            uuid_ids = {}
            try:
                client = Client(url, cache=None, timeout=80)
                invoices_obj = client.factory.create("ns0:UUID")
                invoices_obj._UUID=inv.cfdi_uuid
                invoices_obj._FolioSustitucion='' if not inv.uuid_relacionado_id else inv.uuid_relacionado_id
                invoices_obj._Motivo=inv.cfdi_reason_cancel
                UUIDS_list = client.factory.create("ns0:UUIDArray")
                UUIDS_list.UUID.append(invoices_obj)
                response = client.service.cancel(UUIDS_list, username, password, inv.company_id.vat, cer_pem.replace('\n', ''), key_pem)
                logging.info('-- _nomina_cfdi-reques: Cancel received:\n%s', pprint.pformat(response))
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                return False
            try:
                if hasattr(response, 'CodEstatus'):
                    if response.CodEstatus:
                        msg = getCodeStatusSat( response.CodEstatus )
                        inv.l10n_mx_edi_log_error( msg )
                # if not response.Acuse:
                #     inv.l10n_mx_edi_log_error( 'A delay of 2 hours has to be respected before to cancel' )
                for folios in response.Folios:
                    for folio in folios[1]:
                        if folio.EstatusUUID in ('201', '202'):
                            cancelled = True
                            msg = '%s'%( folio.EstatusCancelacion )
                        else:
                            msg = '%s'%( getCodeStatusSat( folio.EstatusUUID ) )
                        code = folio.EstatusUUID
                xmlacuse = response.Acuse
                xmlacuse = xmlacuse[xmlacuse.find("<CancelaCFDResponse"):xmlacuse.find("</s:Body>")]
                xmlacuse = xmlacuse.replace('<CancelaCFDResponse "', '<CancelaCFDResponse xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance " ')
                acuse = xmlacuse
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                msg = str(e)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                msg = str(e)
            return inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg, acuse)                

    @api.multi
    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None, acuse=None):
        '''Post process the results of the cancel service.
        :param cancelled: is the cancel has been done with success
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''
        self.ensure_one()
        if cancelled:
            body_msg = _('The cancel service has been called with success')
            if acuse:
                base64_str = base64.encodestring(('%s'%(acuse)).encode()).decode().strip()
                ctx = self.env.context.copy()
                ctx.pop('default_type', False)
                filename = "cancelacion_%s.xml"%(self.cfdi_uuid or "")
                attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                    'name': filename,
                    'res_id': self.id,
                    'res_model': self._name,
                    'datas': base64_str,
                    'datas_fname': filename,
                    'description': 'Cancel Mexican CFDI',
                    'mimetype': 'application/xml'
                })
                self.message_post(
                    body=_('Cancel CFDI document'),
                    attachment_ids=[attachment_id.id],
                    subtype='account.mt_invoice_validated')

        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg))
        return cancelled
