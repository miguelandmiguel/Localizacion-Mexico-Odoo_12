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

import unicodedata

_logger = logging.getLogger(__name__)

CATALOGO_TIPONOMINA = [('O','Ordinaria'), ('E','Extraordinaria')]

def remove_accents(s):
    def remove_accent1(c):
        return unicodedata.normalize('NFD', c)[0]
    return u''.join(map(remove_accent1, s))


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

    #----------------------
    # Aplicacion Banorte
    #----------------------
    application_date_banorte = fields.Date('Fecha Aplicacion Pago (Banorte)', required=False, index=True)

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


    #---------------------------------------
    #  Calcular Nominas
    #---------------------------------------
    @api.model
    def _compute_sheet_run_task_payslip(self, use_new_cursor=False, active_id=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
            _logger.info('------ Calcular Nomina %s '%(active_id) )
            payslipModel = self.env['hr.payslip'].browse(active_id).compute_sheet()
            if use_new_cursor:
                cr.commit()
                cr.close()
        return {}

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
                    run_id._compute_sheet_run_task_payslip(use_new_cursor=use_new_cursor, active_id=payslip.id)
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
                        payslip.with_context(without_compute_sheet=True).action_payslip_done()
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
                        if payslip.l10n_mx_edi_cfdi_uuid and payslip.employee_id.address_home_id.email:
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



    #---------------------------------------
    #  Dispersion Nominas Banorte
    #---------------------------------------
    @api.multi
    def dispersion_banorte_datas(self):
        for run_id in self:
            #---------------
            # Header Data 
            #---------------
            banco_header = run_id.company_id.clave_emisora or ''
            run_id.application_date_banorte or 'AAAAMMDD'
            date1 = run_id.application_date_banorte.strftime("%Y%m%d")
            indx = 0
            monto_banco = 0.0
            # ---------------
            # Detalle
            # ---------------
            res_banco_header, res_banco = [], []
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'banorte')
            _logger.info('---------- Layout Banorte %s '%( len(p_ids) ) )
            for slip in p_ids:
                total = slip.get_salary_line_total('C99')
                if total <= 0:
                    continue
                employee_id = slip.employee_id or False
                bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
                if not bank_account_id:
                    continue
                    # raise UserError(_("El empleado %s No tiene cuenta bancaria . "%(employee_id.cfdi_complete_name) ))
                bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
                if not bank_number:
                    continue
                    # raise UserError(_("El Banco Receptor %s no tiene codigo. "%(bank_account_id.name) ))
                indx += 1
                bank_type = '01'
                if bank_number != '072':
                    bank_type = '40'
                cuenta = bank_account_id and bank_account_id.acc_number or ''
                cuenta = cuenta[ : len(cuenta) -1 ]
                cuenta = cuenta[-10:]
                monto_banco += total
                pp_total = '%.2f'%(total)
                pp_total = str(pp_total).replace('.', '')
                res_banco.append((
                    'D',
                    '%s'%( date1 ),
                    '%s'%( str( employee_id.cfdi_code_emp or '' ).rjust(10, "0") ),
                    '%s'%( str(' ').rjust(40, " ") ),
                    '%s'%( str(' ').rjust(40, " ") ),
                    '%s'%( pp_total.rjust(15, "0") ),
                    '%s'%( bank_number ),
                    '%s'%( bank_type ),
                    '%s'%( cuenta.rjust(18, "0") ),
                    '0',
                    ' ',
                    '00000000',
                    '%s'%( str(' ').rjust(18, " ") ),
                ))
            if res_banco:
                monto_banco = '%.2f'%(monto_banco)
                monto_banco = str(monto_banco).replace('.', '')
                res_banco_header = [(
                    'H',
                    'NE',
                    '%s'%( banco_header ),
                    '%s'%( date1 ),
                    '01',
                    '%s'%( str(indx).rjust(6, "0") ),
                    '%s'%( monto_banco.rjust(15, "0") ),
                    '000000',
                    '000000000000000',
                    '000000',
                    '000000000000000',
                    '000000',
                    '0',
                    '%s'%( str(' ').rjust(77, " ") )
                )]
            banco_datas = self._save_txt(res_banco_header + res_banco)
            return banco_datas

    def _save_txt(self, data):
        file_value = ''
        for items in data:
            file_row = ''
            for indx, item in enumerate(items):
                file_row += u'%s'%item
            file_value += file_row + '\r\n'
        return file_value

    #---------------------------------------
    #  Dispersion Nominas BBVA
    #---------------------------------------
    @api.multi
    def dispersion_bbva_datas(self):
        for run_id in self:
            res_banco = []
            indx = 1
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'bbva')
            _logger.info('---------- Layout BBVA %s '%( len(p_ids) ) )
            for slip in p_ids:
                employee_id = slip.employee_id or False
                total = slip.get_salary_line_total('C99')
                if total <= 0:
                    _logger.info('---- Dispersion BBVA NO total=0 %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
                if not bank_account_id:
                    _logger.info('---- Dispersion BBVA NO bank_account_id %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
                cuenta = bank_account_id and bank_account_id.acc_number or ''
                if not cuenta:
                    _logger.info('---- Dispersion BBVA NO CUENTA%s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue

                pp_total = '%.2f'%(total)
                pp_total = str(pp_total).replace('.', '')
                rfc = '%s'%('0').rjust(16, "0")
                # nombre = employee_id.cfdi_complete_name[:40]
                nombre = '%s %s %s'%( employee_id.cfdi_appat, employee_id.cfdi_apmat, employee_id.name )
                nombre = remove_accents(nombre[:40])
                res_banco.append((
                    '%s'%( str(indx).rjust(9, "0") ),
                    rfc,
                    '%s'%( '99' if bank_number == '012' else '40' ),
                    '%s'%( cuenta.ljust(20, " ") ),
                    '%s'%( pp_total.rjust(15, "0") ),
                    '%s'%( nombre.ljust(40, " ") ),
                    '001',
                    '001'
                ))
                indx += 1
            banco_datas = self._save_txt(res_banco)
            return banco_datas

    #---------------------------------------
    #  Dispersion Nominas BBVA
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_datas(self):
        for run_id in self:
            res_banco = []
            indx = 1
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'bbva_inter')
            _logger.info('---------- Layout BBVA Inter %s '%( len(p_ids) ) )
            for slip in p_ids:
                employee_id = slip.employee_id or False
                total = slip.get_salary_line_total('C99')
                if total <= 0:
                    _logger.info('---- Dispersion BBVA NO total=0 %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
                if not bank_account_id:
                    _logger.info('---- Dispersion BBVA NO bank_account_id %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue
                bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
                cuenta = bank_account_id and bank_account_id.acc_number or ''
                if not cuenta:
                    _logger.info('---- Dispersion BBVA NO CUENTA%s %s %s '%( slip.id, slip.number, employee_id.id ) )
                    continue

                pp_total = '%.2f'%(total)
                pp_total = str(pp_total).replace('.', '')
                rfc = '%s'%('0').rjust(16, "0")
                # nombre = employee_id.cfdi_complete_name[:40]
                nombre = '%s %s %s'%( employee_id.cfdi_appat, employee_id.cfdi_apmat, employee_id.name )
                nombre = remove_accents(nombre[:40])
                res_banco.append((
                    '%s'%( str(indx).rjust(9, "0") ),
                    rfc,
                    '%s'%( '99' if bank_number == '012' else '40' ),
                    '%s'%( cuenta.ljust(20, " ") ),
                    '%s'%( pp_total.rjust(15, "0") ),
                    '%s'%( nombre.ljust(40, " ") ),
                    '%s'%( bank_number ),
                    '001'
                ))
                indx += 1
            banco_datas = self._save_txt(res_banco)
            return banco_datas




class ReportBanorteTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbanortetxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_banorte_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))


class ReportBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvatxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_bbva_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

class ReportBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvaintertxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_bbva_inter_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))