# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools, registry
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.tools.float_utils import float_repr
from odoo.tools.misc import split_every
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError
from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

import threading

_logger = logging.getLogger(__name__)

class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'
    _description = 'Generate payslips for all selected employees'

    def _get_available_contracts_domain(self):
        return [('active', 'in', [True, False]), ('contract_id.state', 'in', ('open', 'close')), ('company_id', '=', self.env.user.company_id.id)]

    def _get_employees(self):
        # YTI check dates too
        return self.env['hr.employee'].search(self._get_available_contracts_domain())

    # employee_ids = fields.Many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees', default=lambda self: self._get_employees(), required=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False,
        default=lambda self: self.env['res.company']._company_default_get() )

    @api.model
    def _compute_sheet_tasks(self, use_new_cursor=False, active_id=False, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        intercompany_uid = None
        context = self._context.copy()
        for run in self.env['hr.payslip.run'].browse(active_id):
            company = run.company_id
            intercompany_uid = company.intercompany_user_id and company.intercompany_user_id.id or False
            context['force_company'] = company.id

        payslipModel = self.env['hr.payslip']
        payslips = []
        for employees_chunk in split_every(1, employee_ids):
            _logger.info('--- Nomina Procesando Employees %s', employees_chunk )
            for employee in self.env['hr.employee'].browse(employees_chunk):
                slip_data = payslipModel.onchange_employee_id(from_date, to_date, employee.id, contract_id=False)
                res = {
                    'employee_id': employee.id,
                    'name': slip_data['value'].get('name'),
                    'struct_id': slip_data['value'].get('struct_id'),
                    'contract_id': slip_data['value'].get('contract_id'),
                    'payslip_run_id': active_id,
                    'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                    'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                    'date_from': from_date,
                    'date_to': to_date,
                    'credit_note': credit_note,
                    'company_id': employee.company_id.id,
                    'cfdi_source_sncf': slip_data['value'].get('cfdi_source_sncf'),
                    'cfdi_amount_sncf': slip_data['value'].get('cfdi_amount_sncf'),
                    'cfdi_tipo_nomina': slip_data['value'].get('cfdi_tipo_nomina'),
                    'cfdi_tipo_nomina_especial': slip_data['value'].get('cfdi_tipo_nomina_especial')
                }
                payslip_id = payslipModel.create(res)
                if use_new_cursor:
                    self._cr.commit()
                payslips.append(payslip_id.id)

        _logger.info('--- Nomina payslips %s ', len(payslips) )
        for slip_chunk in split_every(1, payslips):
            _logger.info('--- Nomina payslip_ids %s ', slip_chunk )
            try:
                payslipModel.with_context(slip_chunk=True).browse(slip_chunk).with_context(context).sudo(intercompany_uid).compute_sheet()
                if use_new_cursor:
                    self._cr.commit()
            except Exception as e:
                _logger.info('------ Error al crear la Nomina %s '%( e ) )
                pass
        if use_new_cursor:
            self._cr.commit()

    @api.model
    def _compute_sheet_threading_task(self, use_new_cursor=False, active_id=False, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            self._compute_sheet_tasks(
                use_new_cursor=use_new_cursor, 
                active_id=active_id, from_date=from_date, to_date=to_date, credit_note=credit_note, employee_ids=employee_ids)
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _compute_sheet_threading(self, active_id=False, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.employees']._compute_sheet_threading_task(
                use_new_cursor=self._cr.dbname, 
                active_id=active_id, from_date=from_date, to_date=to_date, credit_note=credit_note, employee_ids=employee_ids)
            new_cr.close()
            return {}

    def compute_sheet(self):
        [data] = self.read()
        if not data['employee_ids']:
            employees = self.with_context(active_test=False).employee_ids
            data['employee_ids'] = employees.ids
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        threaded_calculation = threading.Thread(target=self._compute_sheet_threading, args=(active_id, from_date, to_date, run_data.get('credit_note'), data['employee_ids']))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def compute_sheet_all(self):
        for rec in self:
            employee_ids = self.env['hr.employee'].search([
                ('company_id', '=', rec.company_id.id),
                ('contract_id.state', 'in', ['open', 'close'])
            ])
            rec.write({
                'employee_ids': [(6, 0, employee_ids.ids)]
            })
            rec.compute_sheet()





    @api.multi
    def compute_sheet_old(self):
        payslips = self.env['hr.payslip']
        [data] = self.read()
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        for employee in self.env['hr.employee'].browse(data['employee_ids']):
            slip_data = self.env['hr.payslip'].onchange_employee_id(from_date, to_date, employee.id, contract_id=False)
            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': slip_data['value'].get('contract_id'),
                'payslip_run_id': active_id,
                'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                'date_from': from_date,
                'date_to': to_date,
                'credit_note': run_data.get('credit_note'),
                'company_id': employee.company_id.id,
                'cfdi_source_sncf': slip_data['value'].get('cfdi_source_sncf'),
                'cfdi_amount_sncf': slip_data['value'].get('cfdi_amount_sncf'),
                'cfdi_tipo_nomina': slip_data['value'].get('cfdi_tipo_nomina'),
                'cfdi_tipo_nomina_especial': slip_data['value'].get('cfdi_tipo_nomina_especial')
            }
            payslips += self.env['hr.payslip'].create(res)
        payslips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}

