# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class report_xlsx_wiz(models.TransientModel):
    _name = "report.xlsx.wiz"

    name = fields.Char(string='Name')

    @api.multi
    def action_report_demo(self):
        datas = [
            ['id', 'name', 'address']
        ]

        return self.action_report_xlsx(datas=datas, columns=[], formats=[], report_name="Hoja 1", header=False, freeze_panes=False)


    @api.multi
    def action_report_xlsx(self, datas=[], columns=[], formats=[], report_name="Hoja 1", header=False, freeze_panes=False):
        ctx = {
            'report_name': report_name,
            'datas': datas,
            'header': header,
            'freeze_panes': freeze_panes,
            'columns': columns,
            'formats': formats
        }
        res =  self.env.ref('bias_base_report.report_xlsx_wiz').with_context(**ctx).report_action(self, data=ctx)
        return res
