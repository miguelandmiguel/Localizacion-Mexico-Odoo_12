# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import base64
from itertools import groupby
import re
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO
import requests
from pytz import timezone

from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client

from odoo import _, api, fields, models, tools
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

CFDI_TEMPLATE_33 = 'l10n_mx_edi.cfdiv33'
CFDI_TEMPLATE_40 = 'l10n_mx_edi_40.cfdiv40'
CFDI_XSLT_CADENA = 'l10n_mx_edi_40/data/%s/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi_40/data/xslt/%s/cadenaoriginal_TFD_1_1.xslt'

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


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    l10n_mx_edi_export = fields.Selection([
        ('01', '[01] No aplica'),
        ('02', '[02] Definitiva con clave A1'),
        ('03', '[03] Temporal'),
        ('04', '[04] Clave distinta a A1 o enajenación en términos del CFF'),
    ], 'Exportacion', default='01',
        help='Atributo requerido para expresar si el comprobante ampara una'
             'operación de exportación.')
    l10n_mx_edi_usage = fields.Selection(selection_add=[('S01', '[S01] Sin efectos fiscales.  ')], default="G01")

    @api.multi
    def _l10n_mx_edi_get_payment_policy(self):
        self.ensure_one()
        version = self.l10n_mx_edi_get_pac_version()
        term_ids = self.payment_term_id.line_ids
        if version == '3.2':
            if len(term_ids.ids) > 1:
                return 'Pago en parcialidades'
            else:
                return 'Pago en una sola exhibición'
        elif version in ['3.3', '4.0'] and self.date_due and self.date_invoice:
            if self.type == 'out_refund':
                return 'PUE'
            # In CFDI 3.3 - rule 2.7.1.43 which establish that
            # invoice payment term should be PPD as soon as the due date 
            # is after the last day of  the month (the month of the invoice date).
            if self.date_due.month > self.date_invoice.month or \
               self.date_due.year > self.date_invoice.year or \
               len(term_ids) > 1:  # to be able to force PPD
                return 'PPD'
            return 'PUE'
        return ''

    @api.multi
    def _l10n_mx_edi_create_taxes_cfdi_values(self):
        '''Create the taxes values to fill the CFDI template.
        '''
        self.ensure_one()
        values = {
            'total_withhold': 0,
            'total_transferred': 0,
            'withholding': [],
            'transferred': [],
        }
        taxes = {}
        for line in self.invoice_line_ids.filtered('price_subtotal'):
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            taxes_line = line.invoice_line_tax_ids
            taxes_line = taxes_line.filtered(lambda tax: tax.amount_type != 'group') + taxes_line.filtered(lambda tax: tax.amount_type == 'group').mapped('children_tax_ids')
            tax_line = {tax['id']: tax for tax in taxes_line.compute_all(price, line.currency_id, line.quantity, line.product_id, line.partner_id)['taxes']}
            for tax in taxes_line.filtered(lambda r: r.l10n_mx_cfdi_tax_type != 'Exento'):
                tax_dict = tax_line.get(tax.id, {})
                amount = round(abs(tax_dict.get('amount', tax.amount / 100 * float("%.2f" % line.price_subtotal))), 2)
                base = tax_dict.get('base', line.price_subtotal)
                rate = round(abs(tax.amount), 2)
                if tax.id not in taxes:
                    taxes.update({tax.id: {
                        'base': base,
                        'name': (tax.tag_ids[0].name if tax.tag_ids else tax.name).upper(),
                        'amount': amount,
                        'rate': rate if tax.amount_type == 'fixed' else rate / 100.0,
                        'type': tax.l10n_mx_cfdi_tax_type,
                        'tax_amount': tax_dict.get('amount', tax.amount),
                    }})
                else:
                    taxes[tax.id].update({
                        'base': taxes[tax.id]['base'] + amount,
                        'amount': taxes[tax.id]['amount'] + amount
                    })
                if tax.amount >= 0:
                    values['total_transferred'] += amount
                else:
                    values['total_withhold'] += amount
        values['transferred'] = [tax for tax in taxes.values() if tax['tax_amount'] >= 0]
        values['withholding'] = self._l10n_mx_edi_group_withholding(
            [tax for tax in taxes.values() if tax['tax_amount'] < 0])
        return values        

    def l10n_mx_edi_append_addenda(self, xml_signed):
        self.ensure_one()
        addenda = (
            self.partner_id.l10n_mx_edi_addenda or
            self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        if not addenda:
            return xml_signed
        values = {
            'record': self,
        }
        version = self.l10n_mx_edi_get_pac_version()
        nodo_addenda = "http://www.sat.gob.mx/cfd/3"
        if version == "4.0":
            nodo_addenda = "http://www.sat.gob.mx/cfd/4"
        addenda_node_str = addenda.render(values=values).strip()
        if not addenda_node_str:
            return xml_signed
        tree = fromstring(base64.decodestring(xml_signed))
        addenda_node = fromstring(addenda_node_str)
        if addenda_node.tag != '{%s}Addenda'%(nodo_addenda):
            node = etree.Element(etree.QName(nodo_addenda, 'Addenda'))
            node.append(addenda_node)
            addenda_node = node
        tree.append(addenda_node)
        self.message_post(
            body=_('Addenda has been added in the CFDI with success'),
            subtype='account.mt_invoice_validated')
        xml_signed = base64.encodestring(etree.tostring(
            tree, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        attachment_id.write({
            'datas': xml_signed,
            'mimetype': 'application/xml'
        })
        return xml_signed


    @api.multi
    def _l10n_mx_edi_retry(self):
        '''Try to generate the cfdi attachment and then, sign it.
        '''
        version = self.l10n_mx_edi_get_pac_version()
        for inv in self:
            cfdi_values = inv._l10n_mx_edi_create_cfdi()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                # cfdi failed to be generated
                inv.l10n_mx_edi_pac_status = 'retry'
                inv.message_post(body=error, subtype='account.mt_invoice_validated')
                continue
            # cfdi has been successfully generated
            inv.l10n_mx_edi_pac_status = 'to_sign'
            filename = ('%s-%s-MX-Invoice-%s.xml' % (
                inv.journal_id.code, inv.number, version.replace('.', '-'))).replace('/', '')
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            inv.l10n_mx_edi_cfdi_name = filename
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            if attachment_id:
                attachment_id.write({
                    'datas': base64.encodestring(cfdi),
                    'mimetype': 'application/xml'
                })
            else:
                attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                    'name': filename,
                    'res_id': inv.id,
                    'res_model': inv._name,
                    'datas': base64.encodestring(cfdi),
                    'datas_fname': filename,
                    'description': 'Mexican invoice',
                    })
                inv.message_post(
                    body=_('CFDI document generated (may be not signed)'),
                    attachment_ids=[attachment_id.id],
                    subtype='account.mt_invoice_validated')
            inv._l10n_mx_edi_sign()        

    @api.multi
    def _l10n_mx_edi_create_cfdi(self):
        '''Creates and returns a dictionnary containing 'cfdi' if the cfdi is well created, 'error' otherwise.
        '''
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()
        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))
        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

        # -Compute date and time of the invoice
        time_invoice = datetime.strptime(self.l10n_mx_edi_time_invoice,
                                         DEFAULT_SERVER_TIME_FORMAT).time()
        # -----------------------
        # Create the EDI document
        # -----------------------
        version = self.l10n_mx_edi_get_pac_version()
        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.date_invoice), time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        xsd_cached = "l10n_mx_edi.xsd_cached_cfdv33_xsd"
        cfdi_template = CFDI_TEMPLATE_33
        if version == '4.0':
            cfdi_template = CFDI_TEMPLATE_40
            xsd_cached = "l10n_mx_edi.xsd_cached_cfdv40_xsd"

        # -Compute cfdi
        cfdi = qweb.render(cfdi_template, values=values)
        cfdi = cfdi.replace(b'xmlns__', b'xmlns:')
        node_sello = 'Sello'
        attachment = self.env.ref(xsd_cached, False)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b''

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
        tree.attrib[node_sello] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # Check with xsd
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (IOError, ValueError):
                _logger.info(
                    _('The xsd file to validate the XML structure was not found'))
            except Exception as e:
                return {'error': (_('The cfdi generated is not valid') +
                                    create_list_html(str(e).split('\\n')))}
        xml = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        return {'cfdi': xml}




