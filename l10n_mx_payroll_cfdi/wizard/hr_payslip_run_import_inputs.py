# -*- coding: utf-8 -*-

import time
import logging
from odoo import _, api, fields, models, tools, registry
from odoo.tests.common import Form

from PyPDF2 import PdfFileReader
import io
from odoo.tools import pycompat
import base64
import csv

import threading

_logger = logging.getLogger(__name__)

class HrPayslipRunImportInputsWizard(models.TransientModel):
    _name = 'hr.payslip.run.import.inputs'
    _description = 'Import Your Inputs from Files.'

    attachment_ids = fields.Many2many('ir.attachment', string='Files')
    run_id = fields.Many2one(string="Batch", comodel_name="hr.payslip.run")

    @api.multi
    def action_create_compute_inputsline(self):
        def _get_attachment_filename(attachment):
            return hasattr(attachment, 'fname') and getattr(attachment, 'fname') or attachment.name
        def _get_attachment_content(attachment):
            return hasattr(attachment, 'content') and getattr(attachment, 'content') or base64.b64decode(attachment.datas)

        dataLines = []
        dataHeaders = {}
        inputCode = self.env['hr.rule.input.code']
        for attachment in self.attachment_ids:
            filename = _get_attachment_filename(attachment)
            content = _get_attachment_content(attachment)
            buffer = io.BytesIO(content)
            if filename.lower().strip().endswith('.csv'):
                indx = 0
                lines = pycompat.csv_reader(buffer)
                for line in lines:
                    if indx == 3:
                        for i, headerLine in enumerate(line):
                            if i < 5:
                                continue
                            code = headerLine.strip().split(' ')
                            for code_id in inputCode.search(['|', ('name', 'ilike', headerLine.strip()), ('name', '=', code[0])]):
                                dataHeaders[ i ] = {
                                    'name': headerLine.strip(),
                                    'id': code_id.id,
                                    'input_id': code_id.input_id.id,
                                    'input_name': code_id.input_id.name,
                                    'input_code': code_id.input_id.code,
                                }
                        _logger.info('------ dataHeaders %s '%dataHeaders )
                    if indx >= 4:
                        dataLines.append( line )
                    indx += 1
            buffer.close()

        # Crea Nominas Empleados
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        credit_note = run_data.get('credit_note')

        threaded_calculation = threading.Thread(
            target=self._action_create_compute_inputsline, 
            args=(active_id, from_date, to_date, credit_note, dataLines, dataHeaders), 
            name='crearcalcularrunid_%s'%active_id)
        threaded_calculation.start()

        return True

    def _action_create_compute_inputsline(self, active_id, from_date=False, to_date=False, credit_note=False, dataLines=[], dataHeaders={}):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self._action_create_compute_inputsline_task(
                use_new_cursor=self._cr.dbname, 
                active_id=active_id,
                from_date=from_date, 
                to_date=to_date,
                credit_note=credit_note,
                dataLines=dataLines,
                dataHeaders=dataHeaders)
            new_cr.close()
        return {}

    @api.model
    def _action_create_compute_inputsline_task(self, use_new_cursor=False, active_id=False, from_date=False, to_date=False, credit_note=False, dataLines=[], dataHeaders={}):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME
            runModel = self.env['hr.payslip.run']
            payslipModel = self.env['hr.payslip']
            employeeModel = self.env['hr.employee']
            payslips = []

            # Crea Nominas
            for dataLine in dataLines:
                for employee in employeeModel.search([('identification_id', '=', dataLine[1])]):
                    p_id = payslipModel.search([('payslip_run_id', '=', active_id), ('employee_id', '=', employee.id)])
                    if p_id:
                        payslips.append(p_id.id)
                        continue

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
                    payslips.append(payslip_id.id)
                    if use_new_cursor:
                        self._cr.commit()

            # Calcula Nominas
            run_id = self.env['hr.payslip.run'].browse(active_id)
            for payslip in run_id.slip_ids:
                payslip.compute_sheet()
                if use_new_cursor:
                    self._cr.commit()

            for dataLine in dataLines:
                self.action_create_inputsline_payslip(dataLine=dataLine, dataHeaders=dataHeaders)
                if use_new_cursor:
                    self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception as e:
                    _logger.info('---------Error en proceso Nomina incidencias %s '%e)
                    pass
        return {}

    @api.multi
    def action_create_inputsline(self):
        def _get_attachment_filename(attachment):
            return hasattr(attachment, 'fname') and getattr(attachment, 'fname') or attachment.name
        def _get_attachment_content(attachment):
            return hasattr(attachment, 'content') and getattr(attachment, 'content') or base64.b64decode(attachment.datas)
        inputCode = self.env['hr.rule.input.code']
        for attachment in self.attachment_ids:
            filename = _get_attachment_filename(attachment)
            content = _get_attachment_content(attachment)
            buffer = io.BytesIO(content)
            headers = []
            dataHeaders = {}
            if filename.lower().strip().endswith('.csv'):
                try:
                    indx = 0
                    lines = pycompat.csv_reader(buffer)
                    for line in lines:
                        if indx == 3:
                            for i, headerLine in enumerate(line):
                                if i < 5:
                                    continue
                                code = headerLine.strip().split(' ')
                                for code_id in inputCode.search(['|', ('name', 'ilike', headerLine.strip()), ('name', '=', code[0])]):
                                    dataHeaders[ i ] = {
                                        'name': headerLine.strip(),
                                        'id': code_id.id,
                                        'input_id': code_id.input_id.id,
                                        'input_name': code_id.input_id.name,
                                        'input_code': code_id.input_id.code,
                                    }
                            _logger.info('------ dataHeaders %s '%dataHeaders )
                        if indx >= 4:
                            self.action_create_inputsline_payslip(dataLine=line, dataHeaders=dataHeaders)
                        indx += 1
                except Exception as e:
                    _logger.info('---------error %s '%e)
                    pass
            buffer.close()
        return True
    
    def action_create_inputsline_payslip(self, dataLine=False, dataHeaders=False):
        if not dataLine:
            return False
        payslipInput = self.env['hr.payslip.input']
        where = [('employee_id.identification_id', '=', dataLine[1]), ('payslip_run_id', '=', self.run_id.id)]
        for payslip_id in self.env['hr.payslip'].search(where):
            for indx, lineCode in enumerate(dataLine):
                if indx < 5:
                    continue
                if dataHeaders.get( indx ):
                    _logger.info('-------------- line [%s] %s - %s '%(indx, lineCode, dataHeaders[indx]) )
                    whereInput = [('payslip_id', '=', payslip_id.id), ('code', '=', dataHeaders[indx].get('input_code') )]
                    for input_id in payslipInput.search(whereInput):
                        input_id.write({
                            'amount':  float(lineCode.replace(',', ''))
                        })
                else:
                    continue
        return True

