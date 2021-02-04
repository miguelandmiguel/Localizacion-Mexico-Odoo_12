# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

#----------------------------------------------------------
# Entries
#----------------------------------------------------------

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.multi
    @api.depends('line_ids.debit', 'line_ids.credit')
    def _amount_debit_credit_compute(self):
        for move in self:
            total_debit = 0.0
            total_credit = 0.0
            for line in move.line_ids:
                total_debit += line.debit
                total_credit += line.credit
            move.amount_debit = total_debit
            move.amount_credit = total_credit
    amount_debit = fields.Monetary(compute='_amount_debit_credit_compute',)
    amount_credit = fields.Monetary(compute='_amount_debit_credit_compute',)