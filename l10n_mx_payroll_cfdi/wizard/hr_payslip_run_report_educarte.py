# -*- coding: utf-8 -*-

import time
import logging
from odoo import _, api, fields, models, tools, registry
from odoo.tests.common import Form

import base64
import csv

import threading

_logger = logging.getLogger(__name__)

class HrPayslipRunReportEducarteWizard(models.TransientModel):
    _name = 'hr.payslip.run.report.educarte'
    _description = 'Reporte de Nomina Educarte.'


    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
        default=lambda self: self.env['res.company']._company_default_get() )
    run_id = fields.Many2one(string="Batch", comodel_name="hr.payslip.run")


    def action_create_reports(self):
        return self.env.ref('l10n_mx_payroll_cfdi.hr_payslip_educarte').report_action(self.run_id, data=[])


    def _getReportNameEducarte(self):
        return self.run_id.name