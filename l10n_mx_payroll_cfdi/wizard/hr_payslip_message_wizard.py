# -*- coding: utf-8 -*-

import time, datetime
from dateutil.relativedelta import relativedelta
import logging
from suds.client import Client
import requests

from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)

class hrPayslipMessageWizard(models.TransientModel):
    _name = "hr.payslip.message.wizard"
    _description = "Payslip Messages Wizard "

    run_id = fields.Many2one('hr.payslip.run', string='Procesamiento de Nomina', required=True)
    lines_ids = fields.One2many('hr.payslip.message.wizard.lines', 'wizrun_id', 'Lines')

    @api.model
    def default_get(self, fields):
        res = super(hrPayslipMessageWizard, self).default_get(fields)
        if 'run_id' in fields:
            res['run_id'] = self.env.context.get('active_id')
        if 'lines_ids' in fields:
            messageModel = self.env['mail.message']
            payslip_id = self.env['hr.payslip']
            payslip_ids = self.env['hr.payslip']
            run_id = self.env['hr.payslip.run'].browse( self.env.context.get('active_id') )
            vals = []
            for payslip in run_id.slip_ids.filtered(lambda line: line.state == 'done' and not line.l10n_mx_edi_cfdi_uuid ):
                for message_id in messageModel.search([
                        ('model', '=', 'hr.payslip'), 
                        ('res_id', '=', payslip.id),
                        ('body', 'like', u'El cfdi generado no es válido')], limit=1):
                    body = message_id.body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_COMPLEX_TYPE_4: Element '{http://www.sat.gob.mx/nomina12}""", "'")
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_MININCLUSIVE_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_PATTERN_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", '')
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_DATATYPE_VALID_1_2_1: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                    _logger.info('-------- message_id %s '%(message_id) )
                    vals_tmp = {
                        'name': payslip.number,
                        'wizrun_id': self.id,
                        'payslip_id': payslip.id,
                        'message_id': message_id.id,
                        'body': '%s'%( body )
                    }
                    vals.append((0, 0, vals_tmp))
            for payslip in run_id.slip_ids.filtered(lambda line: line.state in ['draft', 'verify']):
                for message_id in messageModel.search([
                        ('model', '=', 'hr.payslip'), 
                        ('res_id', '=', payslip.id),
                        ('body', 'like', u'Error: Validacion XML')], limit=1):
                    body = message_id.body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_COMPLEX_TYPE_4: Element '{http://www.sat.gob.mx/nomina12}""", "'")
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_MININCLUSIVE_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_PATTERN_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", '')
                    body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_DATATYPE_VALID_1_2_1: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                    _logger.info('-------- message_id %s '%(message_id) )
                    vals_tmp = {
                        'name': payslip.number,
                        'wizrun_id': self.id,
                        'payslip_id': payslip.id,
                        'message_id': message_id.id,
                        'body': '%s'%( body )
                    }
                    vals.append((0, 0, vals_tmp))
            res.update({'lines_ids': vals})
        return res


class hrPayslipMessageWizardLines(models.TransientModel):
    _name = "hr.payslip.message.wizard.lines"
    _description = "Payslip Messages Wizard Lines"

    name = fields.Char('Name')
    body = fields.Html('Body')
    wizrun_id = fields.Many2one("hr.payslip.message.wizard", "Wizard", ondelete="cascade")
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    message_id = fields.Many2one('mail.message', string='Message')

