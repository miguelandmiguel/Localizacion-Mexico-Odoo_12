# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrSalaryRuleGroup(models.Model):
    _name = "hr.salary.rule.group"

    name = fields.Char(string="Nombre", required=True)

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    cfdi_tipo_id = fields.Many2one('l10n_mx_payroll.tipo', string=u"Tipo", oldname="tipo_id")
    cfdi_tipohoras_id = fields.Many2one("l10n_mx_payroll.tipo_horas", string="Tipo horas extras", oldname="tipo_horas_id")
    cfdi_gravado_o_exento = fields.Selection([
                ('gravado','Gravado'), 
                ('exento','Exento'),
                ('ninguno', 'Ninguno')], 
            string="Gravado o exento", required=True, default="gravado", oldname="gravado_o_exento")
    cfdi_codigoagrupador_id = fields.Many2one('l10n_mx_payroll.codigo_agrupador', string=u"Código Agrupador", oldname="codigo_agrupador_id")
    cfdi_agrupacion_id = fields.Many2one('hr.salary.rule.group', string='Agrupacion', oldname="agrupacion_id")
    cfdi_appears_onpayslipreport = fields.Boolean('Appears on Payslip Report', default=False, oldname="appears_on_payslip_report",
        help="Used to display the salary rule on payslip report.")

class HrContract(models.Model):
    _inherit = "hr.contract"

    cfdi_regimencontratacion_id = fields.Many2one('l10n_mx_payroll.regimen_contratacion', string=u"Régimen Contratación", oldname="regimen_contratacion_id")
    cfdi_periodicidadpago_id = fields.Many2one("l10n_mx_payroll.periodicidad_pago", string=u"Periodicidad pago", oldname="periodicidad_pago_id")
    is_cfdi = fields.Boolean(default=True, string="Es CFDI?")

class HrContractType(models.Model):
    _inherit = "hr.contract.type"

    code = fields.Char(string=u"Codigo Catalogo SAT", required=True, default='')

class HrJob(models.Model):
    _inherit = "hr.job"

    cfdi_riesgopuesto_id = fields.Many2one("l10n_mx_payroll.riesgo_puesto", string="Clase riesgo", oldname="riesgo_puesto_id")