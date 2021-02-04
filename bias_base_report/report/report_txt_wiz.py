# -*- coding: utf-8 -*-

from odoo import models
import datetime


class ReportTxt(models.AbstractModel):
    _name = 'report.bias_base_report.report_txt_wiz'
    _inherit = 'report.report_txt.abstract'
    _description = 'Base TXT Report'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        report = objects
        company_id = self.env.user.company_id
        name = report.name
        body = report.txt_body
        txtfile.write(b'%s'%body.encode('utf-8'))