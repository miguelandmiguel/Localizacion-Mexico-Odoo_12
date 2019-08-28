# -*- coding: utf-8 -*-
import functools
import base64
from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client
import json
import logging
import requests

import werkzeug
import werkzeug.exceptions
import werkzeug.utils
import werkzeug.wrappers
import werkzeug.wsgi
from collections import OrderedDict
from werkzeug.urls import url_decode, iri_to_uri

from odoo import api, fields, models, tools, SUPERUSER_ID, exceptions, _
from odoo.exceptions import AccessError, ValidationError
from odoo.exceptions import AccessError, UserError, AccessDenied
from odoo.http import content_disposition, route, dispatch_rpc, request, \
    serialize_exception as _serialize_exception, Response

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"


    @api.model_create_multi
    def create(self, vals_list):
        context = self._context
        if self._context.get('active_model', '') == 'hr.expense':
            model_name = context['active_model']
            model_id = context['active_id']
            for values in vals_list:
                if values.get('name') and values['name'].endswith('.xml') and values.get('datas', b''):
                    cfdi = base64.b64decode(values['datas'])
                    cfdi = fromstring(cfdi)
                    expense_id = self.env[model_name].browse(model_id)
                    res = expense_id.get_validate_xml_cfdi(cfdi)
                    if res.get('type') == None:
                        return super(IrAttachment, self).create(vals_list)
                    elif res.get('type') == 'out':
                        raise exceptions.ValidationError(_("ERROR: No parece ser un XML Valido"))
                    else:
                        raise exceptions.ValidationError(_("ERROR: No parece ser un XML Valido"))
        return super(IrAttachment, self).create(vals_list)

    @api.multi
    def unlink(self):
        if not self:
            return True
        self.check('unlink')
        for expense_attachment in self.filtered(lambda object: object.res_model== 'hr.expense'):
            if expense_attachment.name.endswith('.xml'):
                cfdi = base64.decodestring(expense_attachment.datas)
                cfdi = fromstring(cfdi)
                if not hasattr(cfdi, 'Complemento'):
                    return super(IrAttachment, self).unlink()
                attribute = 'tfd:TimbreFiscalDigital[1]'
                namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
                node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
                tfd_node = node[0] if node else None
                if tfd_node != None:
                    uuid = tfd_node.get('UUID')
                    expense_id = self.env['hr.expense'].browse(expense_attachment.res_id)
                    cfdi_uuid = expense_id.cfdi_uuid or ''
                    expense_id.cfdi_uuid = cfdi_uuid.replace('%s|'%(uuid), '' )
                    message_post = """<span style="color:blue;"><b>Se elimino el XML adjunto con UUID %s</b></span><br />"""%(uuid)
                    expense_id.message_post(body='%s'%message_post )
        res = super(IrAttachment, self).unlink()
        return res



class HrExpense(models.Model):
    _inherit = "hr.expense"

    cfdi_uuid = fields.Char(string='Fiscal Folio', copy=False, readonly=False,
        help='Folio in electronic invoice, is returned by SAT when send to stamp.')

    @api.multi
    def get_validate_xml_cfdi(self, cfdi):
        self.ensure_one()
        company_id = self.env.user.company_id

        # Analiza XML Complemento
        if not hasattr(cfdi, 'Complemento'):
            return {'type': None}

        # Analiza XML Timbre
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        tfd_node = node[0] if node else None
        if tfd_node == None:
            message_post = """<span style="color:red;"><b>NO SE PUDO CARGAR EL XML </b></span><br/><span>El XML no contiene el Timbre Fiscal</span><br />"""
            self.message_post(body='%s'%message_post )
            return {'type': 'out', 'message': 'Error: El XML no contiene el Timbre Fiscal' }
            
        uuid = tfd_node.get('UUID')
        total = cfdi.get('Total', cfdi.get('total'))
        fecha = cfdi.get('Fecha', cfdi.get('fecha'))
        rfc_emisor = cfdi.Emisor.get('Rfc', cfdi.Emisor.get('rfc'))
        rfc_receptor = cfdi.Receptor.get('Rfc', cfdi.Receptor.get('rfc'))
        certificate = cfdi.get('noCertificado', cfdi.get('NoCertificado'))

        # Valido RFC Emisor
        partner_id_vat = ''
        partner_id = self.env['res.partner'].search([('vat', '=', rfc_emisor)], limit=1)
        if not partner_id:
            if self.unit_amount > (company_id.amount_supplier or 0.0):
                message_post = u"""
                    <span style="color:red;">
                        <b>NO SE PUDO CARGAR EL XML </b>
                    </span><br/>
                    <span>El Importe del XML %s es mayor al permitido "%s"</span><br />"""%(self.unit_amount, company_id.amount_supplier)
                self.message_post(body='%s'%message_post )
                return {'type': 'out', 'message': 'El Importe del XML "%s" es mayor al permitido "%s" '%(self.unit_amount, company_id.amount_supplier)  }




        # Valido RFC Receptor
        if company_id.vat != rfc_receptor:
            message_post = u"""
                <span style="color:red;">
                    <b>NO SE PUDO CARGAR EL XML </b>
                </span><br/>
                <span>El RFC del Receptor "%s" es diferente RFC de la Compañia "%s</span><br />"""%(rfc_receptor, company_id.vat)
            self.message_post(body='%s'%message_post )
            return {'type': 'out', 'message': 'Error: El RFC del Receptor "%s" es diferente RFC de la Compañia "%s'%(rfc_receptor, company_id.vat)  }

        # Valido UUID
        uudi_id = self.search([('cfdi_uuid', 'ilike', uuid)])
        if uudi_id:
            message_post = u"""
                <span style="color:red;">
                    <b>NO SE PUDO CARGAR EL XML </b>
                </span><br/>
                <span>Ya existe un documento con el UUID %s """%(uuid)
            self.message_post(body='%s'%message_post )
            return {'type': 'out', 'message': 'Error: Ya existe un documento con el UUID %s '%(uuid) }

        if total and rfc_emisor and rfc_receptor and uuid:
            message_post = """<span><b>Datos del XML</b></span>
            <ul>
                <li><b>RFC Emisor: </b><span>%s</span></li>
                <li><b>RFC Receptor: </b><span>%s</span></li>
                <li><b>RFC Total: </b><span>%s</span></li>
                <li><b>Fecha: </b><span>%s</span></li>
                <li><b>RFC UUID: </b><span>%s</span></li>
                <li><b>Certificado: </b><span>%s</span></li>
            </ul>
            """%(rfc_emisor, rfc_receptor, total, fecha, uuid, certificate)


            xml_signed = base64.encodestring(etree.tostring(cfdi, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
            result = company_id.action_ws_sat(service='validate', params=xml_signed.decode('utf-8'))
            estado = result.get('estado', '')
            if estado == 'Vigente':
                message_post += """
                <ul>
                    <li>XML Valida: %s</li>
                    <li>XML Status: %s</li>
                    <li>XML Cancelable: %s</li>
                    <li>XML Sello Valido: %s</li>
                    <li>XML Estado: %s</li>
                </ul>
                """%(
                    result.get('xml_valido') or '',
                    result.get('cod_estatus') or '',
                    result.get('es_cancelable') or '',
                    result.get('sello_valido') or '',
                    result.get('estado') or '',
                )
                self.message_post(body='%s'%message_post )
            elif result.get('error', ''):
                message_post = """<span style="color:red;" ><b>NO SE PUDO CARGAR EL XML </b></span><br/><span><b>Estado CFDI: </b> %s</span><br />"""%(result['error']) + message_post
                self.message_post(body='%s'%message_post )
                return {'type': 'out', 'message': 'Error: Estado CFDI: %s '%result['error'] }
            self.cfdi_uuid = '%s|'%uuid
        return {'type': None}

