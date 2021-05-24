# -*- coding: utf-8 -*-

import time, datetime
from dateutil.relativedelta import relativedelta
import logging
from pytz import timezone
from suds.client import Client
import requests
from odoo import api, fields, models, tools, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

BANXICO_DATE_FORMAT = '%d/%m/%Y'

_logger = logging.getLogger(__name__)


def rate_retrieve_cop():
    WSDL_URL = 'https://www.superfinanciera.gov.co/SuperfinancieraWebServiceTRM/TCRMServicesWebService/TCRMServicesWebService?WSDL'
    date = time.strftime('%Y-%m-%d')
    try:
        client = Client(WSDL_URL, location=WSDL_URL, faults=True)
        soapresp =  client.service.queryTCRM(date)
        if soapresp["success"] and soapresp["value"]:
            return {
                'COP': [{
                    'fecha': date,
                    'importe': soapresp["value"]
                }]
            }
        return False
    except Exception as e:
        _logger.info("---Error %s "%(str(e)))
        return False
    return False


class CurrencyRate(models.Model):
    _inherit = 'res.currency.rate'
    _name = 'res.currency.rate'

    rate = fields.Float(digits=(12, 10), default=1.0, help='The rate of the currency to the currency of rate 1')

class Currency(models.Model):
    _inherit = "res.currency"

    rate = fields.Float(compute='_compute_current_rate', string='Current Rate', digits=(12, 10),
                        help='The rate of the currency to the currency of rate 1.')

    @api.multi
    @api.depends('rate_ids.rate')
    def _compute_current_rate(self):
        results = super(Currency, self)._compute_current_rate()
        return results


    def getTipoCambioUrl(self, url, fechaIni, fechaFin):
        token = self.env['ir.config_parameter'].sudo().get_param('bmx.token', default='')
        urlHost = '%s/%s/%s'%(url, fechaIni, fechaFin)
        response = requests.get(
            urlHost,
            params={'token': token},
            headers={'Accept': 'application/json', 'Bmx-Token': token, 'Accept-Encoding': 'gzip'},
        )
        json_response = response.json()
        tipoCambios = {}
        for bmx in json_response:
            series = json_response[bmx].get('series') or []
            for serie in series:
                idSerie = serie.get('idSerie') or ''
                if idSerie == 'SF60653':
                    idSerie = 'MXN'
                elif idSerie == 'SF46410':
                    idSerie = 'EUR'
                elif idSerie == 'SF46407':
                    idSerie = 'GBP'
                tipoCambios[idSerie] = []
                for dato in serie.get('datos', []):
                    fecha = datetime.datetime.strptime(dato.get('fecha'), '%d/%m/%Y').date()
                    importe = float(dato.get('dato'))
                    tipoCambios[idSerie].append({
                        'fecha': '%s'%fecha,
                        'importe': importe
                    })
        for tipoeur in tipoCambios.get('EUR', []):
            tipomxn = next(tipomxn for tipomxn in tipoCambios.get('MXN') if tipomxn["fecha"] == tipoeur['fecha'] )
            tipoeur['importe_real'] = tipoeur.get('importe')
            tipoeur['importe'] = tipomxn.get('importe', 0.0) / tipoeur.get('importe', 0.0)

        for tipogbp in tipoCambios.get('GBP', []):
            tipomxn = next(tipomxn for tipomxn in tipoCambios.get('MXN') if tipomxn["fecha"] == tipogbp['fecha'] )
            tipogbp['importe_real'] = tipogbp.get('importe')
            tipogbp['importe'] = tipomxn.get('importe', 0.0) / tipogbp.get('importe', 0.0)
        print('--- tipoCambios ', tipoCambios)
        return tipoCambios

    def getTipoCambio(self, fechaIni, fechaFin, token):
        # url = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF60653,SF46410/datos"
        url = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF60653,SF46410/datos"
        urlHost = '%s/%s/%s'%(url, fechaIni, fechaFin)
        response = requests.get(
            urlHost,
            params={'token': token},
            headers={'Accept': 'application/json', 'Bmx-Token': token, 'Accept-Encoding': 'gzip'},
        )
        json_response = response.json()
        tipoCambios = {}
        for bmx in json_response:
            series = json_response[bmx].get('series') or []
            for serie in series:
                idSerie = serie.get('idSerie') or ''
                if idSerie == 'SF60653':
                    idSerie = 'MXN'
                elif idSerie == 'SF46410':
                    idSerie = 'EUR'
                tipoCambios[idSerie] = []
                for dato in serie.get('datos', []):
                    fecha = datetime.datetime.strptime(dato.get('fecha'), '%d/%m/%Y').date()
                    importe = float(dato.get('dato'))
                    tipoCambios[idSerie].append({
                        'fecha': '%s'%fecha,
                        'importe': importe
                    })
        for tipoeur in tipoCambios.get('EUR', []):
            tipomxn = next(tipomxn for tipomxn in tipoCambios.get('MXN') if tipomxn["fecha"] == tipoeur['fecha'] )
            tipoeur['importe_real'] = tipoeur.get('importe')
            tipoeur['importe'] = tipomxn.get('importe', 0.0) / tipoeur.get('importe', 0.0)
        return tipoCambios

    @api.multi
    def refresh_currency(self, tipoCambios):
        Currency = self.env['res.currency']
        CurrencyRate = self.env['res.currency.rate']
        for moneda in tipoCambios:
            currency_id = Currency.search([('name', '=', moneda)])
            for tipo in tipoCambios[moneda]:
                if tipo['importe'] != 0.0:
                    rate_brw = CurrencyRate.sudo().search([('name', 'like', '%s'%tipo['fecha']), ('currency_id', '=', currency_id.id)])
                    vals = {
                        'name': '%s'%(tipo['fecha']),
                        'currency_id': currency_id.id,
                        'rate': tipo['importe'],
                        'company_id': None
                    }
                    if not rate_brw:
                        CurrencyRate.sudo().create(vals)
                        _logger.info('  ** Create currency %s -- date %s --rate %s ',currency_id.name, tipo['fecha'], tipo['importe'])
                    else:
                        rate_brw.sudo().write(vals)
                        _logger.info('  ** Update currency %s -- date %s --rate %s',currency_id.name, tipo['fecha'], tipo['importe'])
        return True

    def getTipoCambioNO(self, fechaIni, fechaFin, token):
        foreigns = {
            'SF46410': 'EUR',
            'SF60632': 'CAD',
            'SF46406': 'JPY',
            'SF46407': 'GBP',
            'SF60653': 'USD',
        }
        url = 'https://www.banxico.org.mx/SieAPIRest/service/v1/series/%s/datos/%s/%s?token=%s'
        res = requests.get(url % (','.join(foreigns), fechaIni, fechaFin, token))
        res.raise_for_status()
        series = res.json()['bmx']['series']
        series = { foreigns.get( serie['idSerie'] ) : [{'fecha': dato['fecha'], 'importe': float(dato.get('dato') if dato.get('dato') != 'N/E' else '0.0') } for dato in serie['datos']] for serie in series if 'datos' in serie}
        for index, currency in foreigns.items():
            if not series.get(index, False):
                continue
            if currency == 'USD':
                continue
            for tipo in series.get(index, {}):
                tipomxn = next(tipomxn for tipomxn in series.get('SF60653') if tipomxn["fecha"] == tipo['fecha'] )
                tipo['importe_real'] = tipo.get('importe')
                tipo['importe'] = tipomxn.get('importe', 0.0) / tipo.get('importe', 0.0)
        return series

    def run_update_currency_bmx(self, use_new_cursor=False):
        _logger.info(' === Starting the currency rate update cron')
        date_mx = datetime.datetime.now(timezone('America/Mexico_City'))
        today = date_mx.strftime(DEFAULT_SERVER_DATE_FORMAT)
        yesterday = (date_mx - datetime.timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT)
        token = self.env['ir.config_parameter'].sudo().get_param('bmx.token', default='')
        try:
            if token:
                tipoCambios = self.getTipoCambio(yesterday, today, token)
                self.refresh_currency(tipoCambios)
        except:
            pass
        _logger.info(' === End the currency rate update cron')
        # try:
        #     tipoCambios = rate_retrieve_cop()
        #     self.refresh_currency(tipoCambios)
        # except:
        #     pass
