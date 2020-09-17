# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pprint

from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class report_wiz_report_xlsx(models.TransientModel):
    _name = "report.wiz.report.xlsx"
    _description = 'Wizard Export xlsx'


class report_wiz_report_txt(models.TransientModel):
    _name = "report.wiz.report.txt"
    _description = 'Wizard Export txt'


class report_xlsx_wiz(models.TransientModel):
    _name = "report.xlsx.wiz"
    _description = 'Report Export xlsx'

    name = fields.Char(string='Name', default="Hoja 1")
    freeze_panes = fields.Boolean(string='Freeze Panes')
    with_header = fields.Boolean(string='With Headers')
    xlsx_datas = fields.Text(string='Xlsx Datas')
    xlsx_columns = fields.Text(string='Xlsx Columns')
    xlsx_formats = fields.Text(string='Xlsx Formats')
    
    @api.multi
    def action_report_xlsx(self):
        res =  self.env.ref('bias_base_report.report_xlsx_wiz').report_action(self, config=False)
        _logger.info('------------ report_xlsx_wiz:\n%s', pprint.pformat(res))
        return res

class report_xlsx_wiz(models.TransientModel):
    _name = "report.txt.wiz"
    _description = 'Report Export txt'

    name = fields.Char(string='Name', default="Report")
    txt_body = fields.Text(string='TXT Body')

    @api.multi
    def action_report_txt(self):
        res =  self.env.ref('bias_base_report.report_txt_wiz').report_action(self, config=False)
        _logger.info('------------ report.xlsx.wiz:\n%s', pprint.pformat(res))
        return res