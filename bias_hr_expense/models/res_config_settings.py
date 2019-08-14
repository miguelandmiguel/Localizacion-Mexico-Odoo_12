# -*- coding: utf-8 -*-

from odoo import api, fields, models


class company(models.Model):
    _inherit = 'res.company'

    supplier_id = fields.Many2one('res.partner', string="Supplier ")
    amount_supplier = fields.Float(string="Monto")



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'


    @api.one
    @api.depends('company_id')
    def _get_supplier_id(self):
        self.supplier_id = self.company_id.supplier_id

    @api.one
    def _set_supplier_id(self):
        if self.supplier_id != self.company_id.supplier_id:
            self.company_id.supplier_id = self.supplier_id

    @api.one
    @api.depends('company_id')
    def _get_amount_supplier(self):
        self.amount_supplier = self.company_id.amount_supplier

    @api.one
    def _set_amount_supplier(self):
        if self.amount_supplier != self.company_id.amount_supplier:
            self.company_id.amount_supplier = self.amount_supplier


    supplier_id = fields.Many2one('res.partner', string="Supplier ", compute='_get_supplier_id', inverse='_set_supplier_id')
    amount_supplier = fields.Float(string="Monto", compute='_get_amount_supplier', inverse='_set_amount_supplier')


    """
    expense_alias_prefix = fields.Char('Default Alias Name for Expenses')
    use_mailgateway = fields.Boolean(string='Let your employees record expenses by email',
                                     config_parameter='hr_expense.use_mailgateway')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update(
            expense_alias_prefix=self.env.ref('hr_expense.mail_alias_expense').alias_name,
        )
        return res

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env.ref('hr_expense.mail_alias_expense').write({'alias_name': self.expense_alias_prefix})

    @api.onchange('use_mailgateway')
    def _onchange_use_mailgateway(self):
        if not self.use_mailgateway:
            self.expense_alias_prefix = False
    """