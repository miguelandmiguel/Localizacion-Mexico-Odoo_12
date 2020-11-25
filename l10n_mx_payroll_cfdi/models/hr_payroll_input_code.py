# -*- coding: utf-8 -*-

import time
import logging
from odoo import api, fields, models, _
from odoo.tests.common import Form

from PyPDF2 import PdfFileReader
import io
from odoo.tools import pycompat
import base64
import csv

_logger = logging.getLogger(__name__)


class HrRuleInputCode(models.Model):
    _name = 'hr.rule.input.code'
    _description = 'Salary Rule Input Code'

    name = fields.Char(string='Codigo Incidencia', required=True)
    input_id = fields.Many2one('hr.rule.input', string='Entradas',
        required=True, help="Salary Rule Input.")

class HrPayslipRunImportInputsWizard(models.TransientModel):
    _name = 'hr.payslip.run.import.inputs'
    _description = 'Import Your Inputs from Files.'

    attachment_ids = fields.Many2many('ir.attachment', string='Files')
    run_id = fields.Many2one(string="Batch", comodel_name="hr.payslip.run")

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
