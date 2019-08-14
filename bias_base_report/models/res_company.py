# -*- coding: utf-8 -*-

import logging
import json
import uuid
import requests

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