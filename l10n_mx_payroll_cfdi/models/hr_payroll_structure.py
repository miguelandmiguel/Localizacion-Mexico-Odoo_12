# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

class HrSalaryRuleGroup(models.Model):
    _name = "hr.salary.rule.group"
    _description = "HR salary rule group"

    name = fields.Char(string="Nombre", required=True)

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    cfdi_tipo_id = fields.Many2one('l10n_mx_payroll.tipo', string=u"Tipo +", oldname="tipo_id")
    cfdi_tipohoras_id = fields.Many2one("l10n_mx_payroll.tipo_horas", string="Tipo Horas Extras +", oldname="tipo_horas_id")
    cfdi_gravado_o_exento = fields.Selection([
                ('gravado','Gravado'), 
                ('exento','Exento'),
                ('ninguno', 'Ninguno')], 
            string="Gravado o exento +", required=True, default="gravado", oldname="gravado_o_exento")
    cfdi_codigoagrupador_id = fields.Many2one('l10n_mx_payroll.codigo_agrupador', string=u"Código Agrupador +", oldname="codigo_agrupador_id")
    cfdi_agrupacion_id = fields.Many2one('hr.salary.rule.group', string='Agrupacion +', oldname="agrupacion_id")


    cfdi_tipo_neg_id = fields.Many2one('l10n_mx_payroll.tipo', string=u"Tipo -")
    cfdi_tipohoras_neg_id = fields.Many2one("l10n_mx_payroll.tipo_horas", string="Tipo Horas Extras -")
    cfdi_gravado_o_exento_neg = fields.Selection([
                ('gravado','Gravado'), 
                ('exento','Exento'),
                ('ninguno', 'Ninguno')], 
            string="Gravado o exento -", required=True, default="gravado")
    cfdi_codigoagrupador_neg_id = fields.Many2one('l10n_mx_payroll.codigo_agrupador', string=u"Código Agrupador -")
    cfdi_agrupacion_neg_id = fields.Many2one('hr.salary.rule.group', string='Agrupacion -')


    cfdi_appears_onpayslipreport = fields.Boolean('Appears on Payslip Report', default=False, oldname="appears_on_payslip_report",
        help="Used to display the salary rule on payslip report.")
    account_debit = fields.Many2one('account.account', 'Debit Account', domain=[('deprecated', '=', False)], company_dependent=True)
    account_credit = fields.Many2one('account.account', 'Credit Account', domain=[('deprecated', '=', False)], company_dependent=True)


    # cfdi_tipo_id
    @api.onchange('cfdi_tipo_id')
    def onchange_cfdi_tipo_id(self):
        if not self.cfdi_tipo_id:
            self.cfdi_tipohoras_id = False
            self.cfdi_codigoagrupador_id = False
            self.cfdi_agrupacion_id = False

    @api.onchange('cfdi_tipo_neg_id')
    def onchange_cfdi_tipo_neg_id(self):
        if not self.cfdi_tipo_neg_id:
            self.cfdi_tipohoras_neg_id = False
            self.cfdi_codigoagrupador_neg_id = False
            self.cfdi_agrupacion_neg_id = False


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

