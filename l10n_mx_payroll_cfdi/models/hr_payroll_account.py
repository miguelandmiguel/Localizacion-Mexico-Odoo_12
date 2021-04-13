#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from odoo.addons import decimal_precision as dp
from odoo.tools.safe_eval import safe_eval

from PyPDF2 import PdfFileWriter, PdfFileReader 

# attach.datas = self._file_read(attach.store_fname, bin_size)
class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    @api.multi
    def postprocess_pdf_report(self, record, buffer):
        if record._name == 'hr.payslip':
            empl_code = record.employee_id.cfdi_code_emp or record.employee_id.identification_id or ''
            if empl_code:
                out = PdfFileWriter()
                file = PdfFileReader(buffer)
                num = file.numPages
                for idx in range(num): 
                    page = file.getPage(idx) 
                    out.addPage(page)
                out.encrypt(empl_code)
                out.write( buffer )
        return super(IrActionsReport, self).postprocess_pdf_report(record, buffer)

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def create_pdfwithpassword(self):
        full_path = self._full_path(self.store_fname)
        for payslip in self.env[ self.res_model ].browse( self.res_id ):
            empl_code = payslip.employee_id.cfdi_code_emp or payslip.employee_id.identification_id or ''
            if empl_code:
                out = PdfFileWriter()
                file = PdfFileReader(full_path)
                num = file.numPages
                for idx in range(num): 
                    page = file.getPage(idx) 
                    out.addPage(page)
                out.encrypt(empl_code)
                with open(full_path, "wb") as f:
                    out.write(f)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    date = fields.Date('Date Account', states={'draft': [('readonly', False)]}, readonly=True,
        help="Keep empty to use the period of the validation(Payslip) date.")
    journal_id = fields.Many2one('account.journal', 'Salary Journal', readonly=True, required=True,
        states={'draft': [('readonly', False)]}, default=lambda self: self.env['account.journal'].search([('type', '=', 'general')], limit=1))
    move_id = fields.Many2one('account.move', 'Accounting Entry', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        if 'journal_id' in self.env.context:
            vals['journal_id'] = self.env.context.get('journal_id')
        return super(HrPayslip, self).create(vals)

    @api.onchange('contract_id')
    def onchange_contract(self):
        super(HrPayslip, self).onchange_contract()
        self.journal_id = self.contract_id.journal_id.id or (not self.contract_id and self.default_get(['journal_id'])['journal_id']) or self.journal_id

    """
    @api.multi
    def action_payslip_cancel(self):
        moves = self.mapped('move_id')
        moves.filtered(lambda x: x.state == 'posted').button_cancel()
        moves.unlink()
        return super(HrPayslip, self).action_payslip_cancel()
    """

    @api.multi
    def action_payslip_done_no(self):
        res = super(HrPayslip, self).action_payslip_done()

        for slip in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = slip.date or slip.date_to
            currency = slip.company_id.currency_id or slip.journal_id.company_id.currency_id

            name = _('Payslip of %s') % (slip.employee_id.name)
            move_dict = {
                'narration': name,
                'ref': slip.number,
                'journal_id': slip.journal_id.id,
                'date': date,
            }
            for line in slip.details_by_salary_rule_category:
                amount = currency.round(slip.credit_note and -line.total or line.total)
                if currency.is_zero(amount):
                    continue
                debit_account_id = line.salary_rule_id.account_debit.id
                credit_account_id = line.salary_rule_id.account_credit.id

                if debit_account_id:
                    debit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=False),
                        'account_id': debit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount > 0.0 and amount or 0.0,
                        'credit': amount < 0.0 and -amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(debit_line)
                    debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

                if credit_account_id:
                    credit_line = (0, 0, {
                        'name': line.name,
                        'partner_id': line._get_partner_id(credit_account=True),
                        'account_id': credit_account_id,
                        'journal_id': slip.journal_id.id,
                        'date': date,
                        'debit': amount < 0.0 and -amount or 0.0,
                        'credit': amount > 0.0 and amount or 0.0,
                        'analytic_account_id': line.salary_rule_id.analytic_account_id.id or slip.contract_id.analytic_account_id.id,
                        'tax_line_id': line.salary_rule_id.account_tax_id.id,
                    })
                    line_ids.append(credit_line)
                    credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            if currency.compare_amounts(credit_sum, debit_sum) == -1:
                acc_id = slip.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Credit Account!') % (slip.journal_id.name))
                adjust_credit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': 0.0,
                    'credit': currency.round(debit_sum - credit_sum),
                })
                line_ids.append(adjust_credit)

            elif currency.compare_amounts(debit_sum, credit_sum) == -1:
                acc_id = slip.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (slip.journal_id.name))
                adjust_debit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': slip.journal_id.id,
                    'date': date,
                    'debit': currency.round(credit_sum - debit_sum),
                    'credit': 0.0,
                })
                line_ids.append(adjust_debit)
            move_dict['line_ids'] = line_ids
            move = self.env['account.move'].create(move_dict)
            slip.write({'move_id': move.id, 'date': date})
            move.post()
        return res

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    total_exento = fields.Float(string='Total Exento', digits=dp.get_precision('Payroll') )
    total_gravado = fields.Float(string='Total Gravado', digits=dp.get_precision('Payroll') )
    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)

    def _get_partner_id(self, credit_account):
        """
        Get partner_id of slip line to use in account_move_line
        """
        # use partner of salary rule or fallback on employee's address
        register_partner_id = self.salary_rule_id.register_id.partner_id
        partner_id = register_partner_id.id or self.slip_id.employee_id.address_home_id.id
        if credit_account:
            if register_partner_id or self.salary_rule_id.account_credit.internal_type in ('receivable', 'payable'):
                return partner_id
        else:
            if register_partner_id or self.salary_rule_id.account_debit.internal_type in ('receivable', 'payable'):
                return partner_id
        return False

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    account_tax_id = fields.Many2one('account.tax', 'Tax')
    account_debit = fields.Many2one('account.account', 'Debit Account', domain=[('deprecated', '=', False)])
    account_credit = fields.Many2one('account.account', 'Credit Account', domain=[('deprecated', '=', False)])

    @api.multi
    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the environement in which to compute the rule
        :return: returns a tuple build as the base/amount computed, the quantity and the rate
        :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix, float(safe_eval(self.quantity, localdict)), 100.0
            except:
                raise UserError(_('Wrong quantity defined for salary rule %s (%s).') % (self.name, self.code))
        elif self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage)
            except:
                raise UserError(_('Wrong percentage base or quantity defined for salary rule %s (%s).') % (self.name, self.code))
        else:
            context = dict(self.env.context)
            try:
                localdict.update({'total_exento': 0.0, 'total_gravado': 0.0})
                safe_eval(self.amount_python_compute, localdict, mode='exec', nocopy=True)
                cfdi_nomina = {'total_gravado': localdict.get("total_gravado"), 'total_exento': localdict.get("total_exento")}
                context.setdefault('cfdi_nomina', {})[self.id] = cfdi_nomina
                self.env.context = context
                return float(localdict['result']), 'result_qty' in localdict and localdict['result_qty'] or 1.0, 'result_rate' in localdict and localdict['result_rate'] or 100.0
            except:
                raise UserError(_('Wrong python code defined for salary rule %s (%s).') % (self.name, self.code))    

class HrContract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    journal_id = fields.Many2one('account.journal', 'Salary Journal')


class HrRuleInput(models.Model):
    _inherit = 'hr.rule.input'
    _description = 'Salary Rule Input'

    @api.multi
    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, "[%s] %s" % (rec.code, rec.name or '')))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        recs = super(HrRuleInput, self).name_search(name, args=args, operator=operator, limit=limit)
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('code', operator, name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

class HrRuleInputCode(models.Model):
    _name = 'hr.rule.input.code'
    _description = 'Salary Rule Input Code'

    name = fields.Char(string='Codigo Incidencia', required=True)
    input_id = fields.Many2one('hr.rule.input', string='Entradas',
        required=True, help="Salary Rule Input.")
