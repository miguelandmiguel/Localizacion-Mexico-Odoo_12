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

    @api.multi
    def unlink(self):
        if not self:
            return True
        self.check('unlink')

        print("self--- ", self.res_model)
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
            return {'type': 'out'}
            
        uuid = tfd_node.get('UUID')
        total = cfdi.get('Total', cfdi.get('total'))
        fecha = cfdi.get('Fecha', cfdi.get('fecha'))
        rfc_emisor = cfdi.Emisor.get('Rfc', cfdi.Emisor.get('rfc'))
        rfc_receptor = cfdi.Receptor.get('Rfc', cfdi.Receptor.get('rfc'))
        certificate = cfdi.get('noCertificado', cfdi.get('NoCertificado'))

        # Valido RFC Emisor

        # Valido RFC Receptor
        company_id = self.env.user.company_id
        if company_id.vat != rfc_receptor:
            message_post = u"""
                <span style="color:red;">
                    <b>NO SE PUDO CARGAR EL XML </b>
                </span><br/>
                <span>El RFC del Receptor "%s" es diferente RFC de la Compañia "%s</span><br />"""%(rfc_receptor, company_id.vat)
            self.message_post(body='%s'%message_post )
            return {'type': 'out'}

        # Valido UUID
        uudi_id = self.search([('cfdi_uuid', 'ilike', uuid)])
        if uudi_id:
            message_post = u"""
                <span style="color:red;">
                    <b>NO SE PUDO CARGAR EL XML </b>
                </span><br/>
                <span>Ya existe un documento con el UUID %s """%(uuid)
            self.message_post(body='%s'%message_post )
            return {'type': 'out'}

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

            # verifica xml
            url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
            headers = {'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta', 'Content-Type': 'text/xml; charset=utf-8'}
            template = """<?xml version="1.0" encoding="UTF-8"?>
    <SOAP-ENV:Envelope xmlns:ns0="http://tempuri.org/" xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
       <SOAP-ENV:Header/>
       <ns1:Body>
          <ns0:Consulta>
             <ns0:expresionImpresa>${data}</ns0:expresionImpresa>
          </ns0:Consulta>
       </ns1:Body>
    </SOAP-ENV:Envelope>"""
            namespace = {'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'}
            params = '?re=%s&amp;rr=%s&amp;tt=%s&amp;id=%s' % (
                tools.html_escape(tools.html_escape(rfc_emisor or '')),
                tools.html_escape(tools.html_escape(rfc_receptor or '')),
                total or 0.0, uuid or '')
            soap_env = template.format(data=params)
            soap_xml = requests.post(url, data=soap_env, headers=headers)
            response = fromstring(soap_xml.text)
            status = response.xpath('//a:Estado', namespaces=namespace)
            for statu in status:
                if statu != 'Vigente':
                    message_post = """<span style="color:red;" ><b>NO SE PUDO CARGAR EL XML </b></span><br/><span><b>Estado CFDI: </b> %s</span><br />"""%(statu) + message_post
                    self.message_post(body='%s'%message_post )
                    return {'type': 'out'}
                if statu == 'Vigente':
                    message_post = "<span><b>Estado CFDI: </b> %s</span><br />"%(statu) + message_post
                    self.message_post(body='%s'%message_post )
                else:
                    message_post = """<span style="color:red;" ><b>NO SE PUDO CARGAR EL XML </b></span><br/><span><b>Estado CFDI: </b> %s</span><br />"""%(statu) + message_post
                    self.message_post(body='%s'%message_post )
                    return {'type': 'out'}
            self.cfdi_uuid = '%s|'%uuid

        return {'type': None}

