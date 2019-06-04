# -*- coding: utf-8 -*-

import babel
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from pytz import timezone

import odoo
from odoo import api, fields, models, tools, _, registry

CATALOGO_TIPONOMINA = [('O','Ordinaria'),('E','Extraordinaria')]


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"
       
    @api.one
    @api.depends('amount', 'salary_rule_id')
    def _get_gravado(self):
        tipo = self.salary_rule_id and self.salary_rule_id.cfdi_gravado_o_exento or 'gravado'
        self.cfdi_gravado = self.total if tipo == 'gravado' else 0.0
        self.cfdi_exento = self.total if tipo == 'exento' else 0.0

    # currency_id = fields.Many2one(related='slip_id.currency_id', string="Currency")
    cfdi_gravado = fields.Float(string="Total Gravado", compute='_get_gravado', oldname="gravado")
    cfdi_exento = fields.Float(string="Total Exento", compute='_get_gravado', oldname="exento")
    
    cfdi_date_from = fields.Date(related='slip_id.date_from', string="De", oldname="date_from")
    cfdi_date_to = fields.Date(related='slip_id.date_to', string="A", oldname="date_to")
    cfdi_codigo_agrupador = fields.Char(related='salary_rule_id.cfdi_codigoagrupador_id.name', string="Código Agrupador", oldname="codigo_agrupador")


class HrPayslip(models.Model):
    _name = "hr.payslip"
    _inherit = ['mail.thread', 'hr.payslip']


    @api.model
    def _default_currency(self):
        currency_id = self.env.user.company_id.currency_id
        return currency_id

    @api.model
    def _default_cfdi_date_payment(self):
        ctx = self._context
        cfdi_date_payment = fields.Date.to_string(date.today().replace(day=1))
        if 'active_model' in ctx:
            run_id = self.env[ctx['active_model']].browse(ctx['active_id'])
            cfdi_date_payment = run_id.cfdi_date_payment
        return cfdi_date_payment

    currency_id = fields.Many2one('res.currency', string='Currency',
            required=True, readonly=True, 
            default=_default_currency, track_visibility='always')
    cfdi_total = fields.Float(string="Total Amount", copy=False, store=True, compute='_compute_total_payslip', oldname="total")
    cfdi_subtotal = fields.Monetary(string="Percepciones (Subtotal)", copy=False, oldname="subtotal")
    cfdi_concept = fields.Char(string="Concepto", copy=False, oldname="concepto")

    cfdi_date_payment = fields.Date(string="Fecha pago", required=True, default=_default_cfdi_date_payment, oldname="fecha_pago")
    cfdi_tipo_nomina_especial = fields.Selection([
            ('ord', 'Nomina Ordinaria'),
            ('ext_nom', 'Nomina Extraordinaria'),
            ('ext_agui', 'Extraordinaria Aguinaldo')],
        string="Tipo Nomina Especial", default="ord", oldname="tipo_nomina_especial")
    cfdi_tipo_nomina = fields.Selection(selection=CATALOGO_TIPONOMINA, string=u"Tipo Nómina", default='O', oldname="tipo_nomina")
    cfdi_retenido = fields.Monetary(string="ISR Retenido", copy=False, oldname="retenido")
    cfdi_descuento = fields.Monetary(string="Deducciones sin ISR (Descuento)", copy=False, oldname="descuento")

    cfdi_source_sncf = fields.Selection([
            ('IP', 'Ingresos propios'),
            ('IF', 'Ingreso federales'),
            ('IM', 'Ingresos mixtos')],
        string="Recurso Entidad SNCF", oldname="source_sncf")
    cfdi_amount_sncf = fields.Monetary(string="Monto Recurso SNCF", oldname="amount_sncf")
    cfdi_monto = fields.Monetary(string="Monto CFDI", copy=False, oldname="monto_cfdi")

    @api.one
    @api.depends('line_ids', 'line_ids.code')
    def _compute_total_payslip(self):
        line_total = 0.0
        if not self.line_ids:
            self.cfdi_total = 0.0
        else:
            for line in self.line_ids:
                if 'total' in str(line.code).lower():
                    self.cfdi_total = line.cfdi_total
                    break
        return True


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['mail.thread', 'hr.payslip.run']
    _description = 'Payslip Batches'
    _order = "date_start desc"

    @api.model
    def _default_currency(self):
        currency_id = self.env.user.company_id.currency_id
        return currency_id

    currency_id = fields.Many2one('res.currency', string='Currency',
            required=True, readonly=True, 
            default=_default_currency, track_visibility='always')
    cfdi_total = fields.Float(string="Total Amount", copy=False, store=True, compute='_compute_total_payslip', oldname="total")
    cfdi_date_payment = fields.Date(string="Fecha pago", required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)), oldname="fecha_pago")

    cfdi_es_sncf = fields.Boolean(string='Entidad SNCF', readonly=True, compute='_compute_cfdi_sncf', oldname="es_sncf")
    cfdi_source_sncf = fields.Selection([
            ('IP', 'Ingresos propios'),
            ('IF', 'Ingreso federales'),
            ('IM', 'Ingresos mixtos')],
        string="Recurso Entidad SNCF", oldname="source_sncf")
    cfdi_amount_sncf = fields.Float(string="Monto Recurso SNCF", oldname="amount_sncf")
    cfdi_eval_state = fields.Boolean('Eval State', compute='_compute_state', oldname="eval_state")
    
    cfdi_concept = fields.Char(string="Concepto", required=True, default="", oldname="concepto")

    cfdi_tipo_nomina_especial = fields.Selection([
            ('ord', 'Nomina Ordinaria'),
            ('ext_nom', 'Nomina Extraordinaria'),
            ('ext_agui', 'Extraordinaria Aguinaldo')],
        string="Tipo Nomina Especial", default="ord", oldname="tipo_nomina_especial")
    cfdi_tipo_nomina = fields.Selection(selection=CATALOGO_TIPONOMINA, string=u"Tipo Nómina", default='O', compute='_compute_cfdi_sncf', oldname="tipo_nomina")

    # Compute
    @api.one
    @api.depends('cfdi_date_payment', 'cfdi_concept', 'slip_ids', 'slip_ids.cfdi_total')
    def _compute_total_payslip(self):
        self.cfdi_total = 0.0

    @api.one
    @api.depends('slip_ids', 'cfdi_source_sncf', 'cfdi_amount_sncf', 'cfdi_tipo_nomina_especial')
    def _compute_cfdi_sncf(self):
        cfdi_tipo_nomina = 'O' if self.cfdi_tipo_nomina_especial == 'ord' else 'E'
        self.cfdi_es_sncf = True if self.cfdi_source_sncf else False
        self.cfdi_tipo_nomina = cfdi_tipo_nomina
        self.sudo().slip_ids.write({
            "cfdi_source_sncf": self.cfdi_source_sncf,
            "cfdi_amount_sncf": self.cfdi_amount_sncf,
            "cfdi_tipo_nomina": cfdi_tipo_nomina,
            "cfdi_tipo_nomina_especial": self.cfdi_tipo_nomina_especial
        })
        return True

    @api.one
    @api.depends('slip_ids', 'slip_ids.state')
    def _compute_state(self):
        eval_state = True if self.eval_state else False
        state = 'draft'
        if len(self.slip_ids) == 0:
            state = 'draft'
        elif any(slip.state == 'draft' for slip in self.slip_ids):  # TDE FIXME: should be all ?
            state = 'draft'
        elif all(slip.state in ['cancel', 'done'] for slip in self.slip_ids):
            state = 'close'
        else:
            state = 'draft'
        self.state = state
        return True


