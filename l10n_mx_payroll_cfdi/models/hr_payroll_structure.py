# -*- coding: utf-8 -*-

from odoo import _, api, fields, models, tools

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    _description = 'Salary Structure'

    @api.model
    def _get_default_report_id(self):
        res = self.env.ref('l10n_mx_payroll_cfdi.hr_payslip_mx', False)
        return res

    report_id = fields.Many2one('ir.actions.report',
        string="Report", domain="[('model','=','hr.payslip'),('report_type','=','qweb-pdf')]", default=_get_default_report_id)


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _inherit = 'hr.payslip.line'

    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)