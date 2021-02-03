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


class RegistroPatronal(models.Model):
    _name = 'l10n_mx_payroll.regpat'
    _description = 'Registro Patronal'
    
    name = fields.Char(string="Name", required=True, default="")
    code = fields.Char(string="Code", size=64, required=True, default="")
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        default=lambda self: self.env['res.company']._company_default_get('l10n_mx_payroll.regpat'))

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(RegistroPatronal, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()