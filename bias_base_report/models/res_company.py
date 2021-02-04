# -*- coding: utf-8 -*-

import base64
from lxml import etree
import logging
import json
from json import dumps, loads
import uuid
import requests
from suds.client import Client
from xmljson import badgerfish as bf

from itertools import groupby
import odoo
from odoo import api, fields, models, tools, exceptions, _

_logger = logging.getLogger(__name__)

DEFAULT_HOST = 'https://odoo10.bias.mx'
DEFAULT_DB = 'odoo10_admin'

#----------------------------------------------------------
# Helpers for clients
#----------------------------------------------------------
class InsufficientCreditError(Exception):
    pass


class AuthenticationError(Exception):
    pass

def jsonrpc(url, method='call', params=None, timeout=15):
    payload = {
        'jsonrpc': '2.0',
        'method': method,
        'params': params,
        'id': uuid.uuid4().hex,
    }
    _logger.info('jsonrpc %s', url)
    try:
        req = requests.post(url, json=payload, timeout=timeout)
        req.raise_for_status()
        response = req.json()
        if 'error' in response:
            name = response['error']['data'].get('name').rpartition('.')[-1]
            message = response['error']['data'].get('message')
            if name == 'InsufficientCreditError':
                e_class = InsufficientCreditError
            elif name == 'AccessError':
                e_class = exceptions.AccessError
            elif name == 'UserError':
                e_class = exceptions.UserError
            else:
                raise requests.exceptions.ConnectionError()
            e = e_class(message)
            e.data = response['error']['data']
            raise e
        return response.get('result')
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.MissingSchema, requests.exceptions.Timeout) as e:
        raise exceptions.AccessError('The url that this service requested returned an error. Please contact the author the app. The url it tried to contact was ' + url)


class company(models.Model):
    _inherit = 'res.company'

    # cfdi_test = fields.Boolean(string='MX PAC test environment', default=True)

    @api.multi
    def action_ws_sat(self, service='', params=None):
        cfdi_host = self.env['ir.config_parameter'].sudo().get_param('cfdi.host', DEFAULT_HOST)
        cfdi_db = self.env['ir.config_parameter'].sudo().get_param('cfdi.db', DEFAULT_DB)
        cfdi_params = {
            "test": "True", # self.cfdi_test,
            "cfdi": params
        }
        _logger.info('res_datas %s', cfdi_params)
        endpoint = "%s/cfdi/%s/%s/%s"%(cfdi_host, service, cfdi_db, self.vat)
        res_datas = jsonrpc(endpoint, params=cfdi_params, timeout=400)
        if res_datas.get('error') and type(res_datas['error']) is str:
            return res_datas
        msg = res_datas.get('error') and res_datas['error'].get('data') and res_datas['error']['data'].get('message')
        if msg:
            return {'error': '%s'%msg}
        if res_datas.get('error') and res_datas['error'].get('message'):
            return {'error': '%s'%res_datas['error']['message']}
        if res_datas.get('result') and res_datas['result'].get('error'):
            return {'error': '%s'%res_datas['result']['error']}
        if res_datas.get('error'):
            return {'error': '%s'%res_datas['error']}
        return res_datas

    @api.multi
    def cfdi_call_service(self, service_type=False, xml64=False):
        for company_id in self:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            pac_service_func = 'cfdi_call_service_%s_%s'%(pac_name, service_type)
            test = company_id.l10n_mx_edi_pac_test_env
            username = company_id.l10n_mx_edi_pac_username
            password = company_id.l10n_mx_edi_pac_password
            if test:
                url = 'http://demo-facturacion.finkok.com/servicios/soap/%s.wsdl'%(service_type)
            else:
                url = 'http://facturacion.finkok.com/servicios/soap/%s.wsdl'%(service_type)
            pac_info = getattr(self, pac_service_func)(test=test, url=url, username=username, password=password, xml64=xml64)
            return pac_info

    def cfdi_call_service_finkok_validation(self, test=False, url=False, username=False, password=False, xml64=False):
        client = Client(url, cache=None, timeout=80)
        contenido = client.service.validate(xml64.decode('utf-8'), username, password)
        try:
            try:
                error = contenido.error
                return {u'error': {u'message': "Error validar XML \n\n %s "%( error.upper() )}}
            except Exception as e:
                if not contenido.sat:
                    return {u'error': {u'message': "No se pudo establecer comunicacion con el SAT. \n Favor de intentar nuevamente."  }}
                return {
                    "xml_valido": contenido.xml,
                    "sello_valido": contenido.sello,
                    "sello_sat_valido": contenido.sello_sat,
                    "estado": str(contenido.sat and contenido.sat.Estado or ''),
                    "cod_estatus": str(contenido.sat and contenido.sat.CodigoEstatus or ''),
                    "xml_datas": self.cfdi_call_service_xml_datas(xml64)
                }
        except Exception as e:
            return {u'error': {u'message': str(e)  }}
        return ""

    def cfdi_call_service_xml_datas(self, xml64):
        datas = {}
        xml = base64.b64decode(xml64).decode('utf-8')
        registrofiscal = xml.find('registrofiscal:CFDIRegistroFiscal xmlns:schemaLocation="http://www.sat.gob.mx/registrofiscal http://www.sat.gob.mx/sitio_internet/cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd"')
        if registrofiscal > 1:
            xml = xml.replace('registrofiscal:CFDIRegistroFiscal xmlns:schemaLocation="http://www.sat.gob.mx/registrofiscal http://www.sat.gob.mx/sitio_internet/cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd"', 'registrofiscal:CFDIRegistroFiscal ')
        registrofiscal = xml.find("registrofiscal:CFDIRegistroFiscal")
        schemaLocation = xml.find('xsi:schemaLocation="http://www.sat.gob.mx/cfd/3 http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd"')
        if registrofiscal > 1 and schemaLocation > 1:
            xml = xml.replace('xsi:schemaLocation="http://www.sat.gob.mx/cfd/3 http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd"', 'xsi:schemaLocation="http://www.sat.gob.mx/cfd/3 http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv32.xsd http://www.sat.gob.mx/registrofiscal http://www.sat.gob.mx/sitio_internet/cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd"')
        datas = dumps(bf.data(etree.fromstring(xml)))
        return datas
