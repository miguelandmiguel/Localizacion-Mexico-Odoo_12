# -*- coding: utf-8 -*-

import time, datetime
from dateutil.relativedelta import relativedelta
import logging
from suds.client import Client
import requests

from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)

class CurrencyWizard(models.TransientModel):
    _name = "currency_rate_update_wizard"

    date_start = fields.Date(string="Fecha Inicial", required=True)
    date_stop = fields.Date(string="Fecha Final", required=True)
    serie_id = fields.Selection([
        ('SF60653', '[SF60653] Dolar'),
        ('SF46410', '[SF46410] Euro'),
        ('SF46407', '[SF46407] Libra esterlina'),
        ('all', 'Todos')
        ], default="SF60653", string="Serie Tipo de Cambio")


    def action_update_rate(self):

        currencyModel = self.env['res.currency']

        url = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
        if self.serie_id == 'SF60653':
            url += '/%s/datos'%(self.serie_id)
        elif self.serie_id != 'all':
            url += '/SF60653,%s/datos'%(self.serie_id)
        else:
            url += 'SF60653,SF46410,SF46407/datos'
        tipoCambios = currencyModel.getTipoCambioUrl(url, self.date_start, self.date_stop)
        currencyModel.refresh_currency(tipoCambios)
        return True

