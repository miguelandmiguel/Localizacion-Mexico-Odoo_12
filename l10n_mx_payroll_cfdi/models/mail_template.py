# -*- coding: utf-8 -*-
import logging
from odoo import api, models
from odoo.tools import pycompat

_logger = logging.getLogger(__name__)

class MailTemplate(models.Model):
    _inherit = "mail.template"

    @api.multi
    def generate_email(self, res_ids, fields=None):
        self.ensure_one()
        res = super(MailTemplate, self.with_context(is_private=True) ).generate_email(res_ids, fields=fields)
        multi_mode = True
        if isinstance(res_ids, pycompat.integer_types):
            res_ids = [res_ids]
            multi_mode = False
            
        if self.model not in ['account.invoice', 'account.payment', 'hr.payslip']:
            return res
        for record in self.env[self.model].browse(res_ids):
            if record.company_id.country_id != self.env.ref('base.mx'):
                continue
            res[record.id]['partner_ids'] = record.employee_id.address_home_id and record.employee_id.address_home_id.ids
            attachment = record.l10n_mx_edi_retrieve_last_attachment()
            if attachment:
                (res[record.id] if multi_mode else res).setdefault('attachments', []).append((attachment.name, attachment.datas))
        return res


class Message(models.Model):
    _inherit = 'mail.message'
    _description = 'Message'

    @api.multi
    def _notify_compute_recipients(self, record, msg_vals):
        res = super(Message, self)._notify_compute_recipients(record, msg_vals)
        recipient_data = {
            'partners': [],
            'channels': [],
        }
        _logger.info('----------- _notify_compute_recipients %s '%( record._name ) )
        if record._name == 'hr.payslip':
            contact_id = record.employee_id.address_home_id.id
            recipient_data['channels'] = res.get('channels')
            for partner in res.get('partners', []):
                if partner['id'] == contact_id:
                    recipient_data['partners'] = [ partner ]
                    break
            _logger.info('------------- _notify_compute_recipients INFO %s  '%( recipient_data ) )
            return recipient_data
        return res
