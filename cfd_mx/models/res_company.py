# -*- coding: utf-8 -*-

import suds
from suds.client import Client

from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    def cfdi_finkok_reportuuid(self, dateFrom, dateTo):
        demo = self.env['ir.config_parameter'].sudo().get_param('host.finkok.demo', default='')
        prod = self.env['ir.config_parameter'].sudo().get_param('host.finkok.prod', default='')

        test = self.l10n_mx_edi_pac_test_env
        username = self.l10n_mx_edi_pac_username
        password = self.l10n_mx_edi_pac_password
        url = prod if not test else prod
        url = "%s/%s"%(url, "utilities.wsdl")
        rfc = self.vat

        print("--------", test, username, password, url, rfc)

        client = Client(url, cache=None, timeout=40)
        response = client.service.report_uuid(username,password,rfc,dateFrom,dateTo)
        if response.invoices is None:
            print("----")
        else:
            for uuid in response.invoices.ReportUUID:
                print("-----------------", uuid)
        
