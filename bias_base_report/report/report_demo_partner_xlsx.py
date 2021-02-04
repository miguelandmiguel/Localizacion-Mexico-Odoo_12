# -*- coding: utf-8 -*-

from odoo import models

class PartnerXlsx(models.AbstractModel):
    _name = 'report.bias_base_report.partner_demo'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Report XLSX Demo'

    def get_workbook_options(self):
        return {'constant_memory': True}

    def generate_xlsx_report(self, workbook, data, partners):
        for obj in partners:
            sheet = workbook.add_worksheet('Report')
            bold = workbook.add_format({'bold': True})
            sheet.write(0, 0, obj.name, bold)