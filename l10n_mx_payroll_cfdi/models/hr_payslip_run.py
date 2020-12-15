# -*- coding: utf-8 -*-
import logging
import threading
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools, registry
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr
from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

_logger = logging.getLogger(__name__)

CATALOGO_TIPONOMINA = [('O','Ordinaria'), ('E','Extraordinaria')]

def create_list_html(array):
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'

class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    @api.depends('slip_ids', 'slip_ids.state', 'slip_ids.l10n_mx_edi_cfdi_uuid')
    def _compute_state(self):
        for rec in self:
            eval_state = True if rec.eval_state else False
            state = 'draft'
            if len(rec.slip_ids) == 0:
                state = 'draft'
            elif any(slip.state == 'draft' for slip in rec.slip_ids):  # TDE FIXME: should be all ?
                state = 'draft'
            elif all(slip.state in ['cancel', 'done'] for slip in rec.slip_ids):
                state = 'close'
            else:
                state = 'draft'
            rec.state = state
        return True

    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=False,
        index=True, store=True, copy=False)  # related is required

    eval_state = fields.Boolean('Eval State', compute='_compute_state')
    cfdi_es_sncf = fields.Boolean(string='Entidad SNCF', readonly=True, default=False, oldname="es_sncf")
    cfdi_source_sncf = fields.Selection([
            ('', ''),
            ('IP', 'Ingresos propios'),
            ('IF', 'Ingreso federales'),
            ('IM', 'Ingresos mixtos')],
        string="Recurso Entidad SNCF", oldname="source_sncf")
    cfdi_amount_sncf = fields.Float(string="Monto Recurso SNCF", oldname="amount_sncf")

    cfdi_date_payment = fields.Date(string="Fecha pago", required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)), oldname="fecha_pago")
    cfdi_tipo_nomina_especial = fields.Selection([
            ('ord', 'Nomina Ordinaria'),
            ('ext_nom', 'Nomina Extraordinaria'),
            ('ext_agui', 'Extraordinaria Aguinaldo')],
        string="Tipo Nomina Especial", default="ord", oldname="tipo_nomina_especial")
    cfdi_tipo_nomina = fields.Selection(selection=CATALOGO_TIPONOMINA, string=u"Tipo Nómina", default='O', oldname="tipo_nomina")
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
        readonly=True, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},
        help='Defines the rules that have to be applied to this payslip, accordingly '
             'to the contract chosen. If you let empty the field contract, this field isn\'t '
             'mandatory anymore and thus the rules applied will be all the rules set on the '
             'structure of all contracts of the employee valid for the chosen period')

    cfdi_btn_compute = fields.Boolean()
    cfdi_btn_confirm = fields.Boolean()
    cfdi_btn_sendemail = fields.Boolean()
    cfdi_btn_clear = fields.Boolean()

    @api.multi
    def write(self, vals):
        line_vals = {}
        if 'cfdi_source_sncf' in vals:
            vals['cfdi_es_sncf'] = True if vals['cfdi_source_sncf'] else False
            line_vals.update({
                'cfdi_source_sncf': vals['cfdi_source_sncf']
            })
        if 'cfdi_amount_sncf' in vals:
            line_vals.update({
                'cfdi_amount_sncf': vals['cfdi_amount_sncf']
            })
        if 'cfdi_tipo_nomina_especial' in vals:
            vals['cfdi_tipo_nomina'] = 'O' if vals['cfdi_tipo_nomina_especial'] == 'ord' else 'E'
            line_vals.update({
                'cfdi_tipo_nomina': 'O' if vals['cfdi_tipo_nomina_especial'] == 'ord' else 'E',
                'cfdi_tipo_nomina_especial': vals['cfdi_tipo_nomina_especial']
            })
        result = super(HrPayslipRun, self).write(vals)
        if line_vals:
            for rec in self:
                rec.slip_ids.write(line_vals)
        return result

    """
    @api.depends('cfdi_source_sncf', 'cfdi_amount_sncf')
    def _compute_cfdi_sncf(self):
        for rec in self:
            print('--------------  _compute_cfdi_sncf')
            rec.cfdi_es_sncf = True if rec.cfdi_source_sncf else False
            rec.slip_ids.write({
                "cfdi_source_sncf": rec.cfdi_source_sncf or '',
                "cfdi_amount_sncf": rec.cfdi_amount_sncf or 0.0
            })

    @api.depends('cfdi_tipo_nomina_especial')
    def _compute_cfdi_tipo_nomina(self):
        for rec in self:
            print('--------- cfdi_tipo_nomina_especial')
            cfdi_tipo_nomina = 'O' if rec.cfdi_tipo_nomina_especial == 'ord' else 'E'
            rec.cfdi_tipo_nomina = cfdi_tipo_nomina
            rec.slip_ids.write({
                "cfdi_tipo_nomina": cfdi_tipo_nomina,
                "cfdi_tipo_nomina_especial": rec.cfdi_tipo_nomina_especial
            })
    """

    """
    @api.depends('cfdi_source_sncf', 'cfdi_amount_sncf', 'cfdi_tipo_nomina_especial')
    def _compute_cfdi_sncf(self):
        for rec in self:
            cfdi_tipo_nomina = 'O' if rec.cfdi_tipo_nomina_especial == 'ord' else 'E'
            rec.cfdi_tipo_nomina = cfdi_tipo_nomina
            rec.slip_ids.write({
                "cfdi_source_sncf": rec.cfdi_source_sncf,
                "cfdi_amount_sncf": rec.cfdi_amount_sncf,
                "cfdi_tipo_nomina": cfdi_tipo_nomina,
                "cfdi_tipo_nomina_especial": rec.cfdi_tipo_nomina_especial
            })
        return True
    """

    #---------------------------------------
    #  Calcular Nominas
    #---------------------------------------
    @api.model
    def _compute_sheet_run_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            for run_id in runModel.browse(active_id):
                for payslip in payslipModel.search([('state', '=', 'draft'), ('payslip_run_id', '=', run_id.id)]):
                    try:
                        _logger.info('------- Compute Payslip %s '%(payslip.id) )
                        payslip.compute_sheet()
                    except Exception as e:
                        payslip.message_post(body='Error Al calcular la Nomina: %s '%( e ) )
                        _logger.info('------ Error Al Calcular  la Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _compute_sheet_run_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._compute_sheet_run_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}

    @api.multi
    def cumpute_sheet_run(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=self._compute_sheet_run_threading, args=(run_id.id, ), name='calcularrunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}


    #---------------------------------------
    #  Confirmar y Timbrar Nominas
    #---------------------------------------
    @api.model
    def _confirm_sheet_run_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            for run_id in runModel.browse(active_id):
                for payslip in payslipModel.search([('state', 'in', ['draft','verify']), ('payslip_run_id', '=', run_id.id)]):
                    try:
                        _logger.info('------- Payslip Done %s '%(payslip.id) )
                        payslip.action_payslip_done()
                    except Exception as e:
                        payslip.message_post(body='Error Al timbrar la Nomina: %s '%( e ) )
                        _logger.info('------ Error Al timbrar  la Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _confirm_sheet_run_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._confirm_sheet_run_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}
    @api.multi
    def confirm_sheet_run(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=run_id._confirm_sheet_run_threading, args=([run_id.id]), name='timbrarrunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}


    #---------------------------------------
    #  Enviar Nominas
    #---------------------------------------
    @api.model
    def _enviar_nomina_threading_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            ctx = self._context.copy()
            template = self.env.ref('l10n_mx_payroll_cfdi.email_template_payroll', False)
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            mailModel = self.env['mail.compose.message']
            for run_id in runModel.browse(active_id):
                for payslip in payslipModel.search([('state', '=', 'done'), ('payslip_run_id', '=', run_id.id)]):
                    try:
                        if payslip.l10n_mx_edi_cfdi_uuid:
                            _logger.info('------- Payslip Email %s '%(payslip.id) )
                            ctx.update({
                                'default_model': 'hr.payslip',
                                'default_res_id': payslip.id,
                                'default_use_template': bool(template),
                                'default_template_id': template.id,
                                'default_composition_mode': 'comment',
                            })
                            vals = mailModel.onchange_template_id(template.id, 'comment', 'hr.payslip', payslip.id)
                            mail_message  = mailModel.with_context(ctx).create(vals.get('value',{}))
                            mail_message.action_send_mail()
                    except Exception as e:
                        payslip.message_post(body='Error Al enviar Email Nomina: %s '%( e ) )
                        _logger.info('------ Error Al enviar Email Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _enviar_nomina_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._enviar_nomina_threading_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}

    @api.multi
    def enviar_nomina(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=self._enviar_nomina_threading, args=(run_id.id, ), name='enviarnominarunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}



    #---------------------------------------
    #  Borrar Nominas en 0
    #---------------------------------------
    @api.model
    def _unlink_sheet_run_threading_task(self, use_new_cursor=False, active_id=False):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            for run_id in runModel.browse(active_id):
                payslip_ids = payslipModel.search([('state', '=', 'draft'), ('payslip_run_id', '=', run_id.id)])
                line_ids = payslip_ids.filtered(lambda line: line.get_salary_line_total('C99') == 0.0)
                _logger.info('-------- Payslip  Unlik %s '%( len(line_ids) ) )
                for payslip in line_ids:
                    try:
                        _logger.info('------- Payslip Unlink %s '%(payslip.id) )
                        payslip.unlink()
                    except Exception as e:
                        payslip.message_post(body='Error Al borrar la Nomina: %s '%( e ) )
                        _logger.info('------ Error Al borrar  la Nomina %s '%( e ) )
                    if use_new_cursor:
                        self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _unlink_sheet_run_threading(self, active_id):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.run']._unlink_sheet_run_threading_task(use_new_cursor=self._cr.dbname, active_id=active_id)
            new_cr.close()
        return {}

    @api.multi
    def unlink_sheet_run(self):
        for run_id in self:
            threaded_calculation = threading.Thread(target=self._unlink_sheet_run_threading, args=(run_id.id, ), name='unlinknominarunid_%s'%run_id.id)
            threaded_calculation.start()
        return {}