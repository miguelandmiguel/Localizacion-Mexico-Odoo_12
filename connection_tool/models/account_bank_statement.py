# -*- coding: utf-8 -*-

import time
import logging
import threading
from odoo import api, fields, models, registry, _, SUPERUSER_ID, tools
from odoo.tools import float_compare


_logger = logging.getLogger(__name__)


def millis():
    milli_sec = int(round(time.time() * 1000))
    return milli_sec

class AccountMove(models.Model):
    _inherit = "account.move"

    @api.multi
    def assert_balanced(self):
        if not self.ids:
            return True
        ctx = self._context
        if ctx.get('ConnectionTool', False) == True:
            return True
        else:
            return super(AccountMove, self).assert_balanced()
        return True


class ResCompany(models.Model):
    _inherit = 'res.company'

    account_import_id = fields.Many2one('account.account', string='Adjustment Account (import)')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.one
    @api.depends('company_id')
    def _get_account_import_id(self):
        self.account_import_id = self.company_id.account_import_id

    @api.one
    def _set_account_import_id(self):
        if self.account_import_id != self.company_id.account_import_id:
            self.company_id.account_import_id = self.account_import_id

   
    account_import_id = fields.Many2one('account.account', compute='_get_account_import_id', inverse='_set_account_import_id', required=False,
        string='Adjustment Account (import)', help="Adjustment Account (import).")


# Validar que no se borren asientos del layout de pagos

class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def getMoveCounterPart(self):
        _logger.info(" INICIA ------------------------")
        AccountMoveLine = self.env["account.move.line"]

        layoutline_id = {
            'movel_line_ids': [29142462, 29142457]
        }
        movel_line_ids = layoutline_id.get('movel_line_ids') and layoutline_id['movel_line_ids'] or []
        line_currency = self.env.user.company_id.currency_id #  st_line.currency_id or st_line.journal_id.currency_id or st_line.company_id.currency_id
        line_residual = -10000 # st_line.currency_id and st_line.amount_currency or st_line.amount
        open_balance_dicts = []
        counterpart_aml_dicts = []
        balance = 0.0
        for aml in AccountMoveLine.browse(movel_line_ids):
            if aml.full_reconcile_id:
                continue
            if round(abs(aml.amount_residual), 2) <= round(abs(line_residual), 2):
                balance += abs(aml.amount_residual)
                counterpart_aml_dicts.append({
                        'name': aml.name if aml.name != '/' else aml.move_id.name,
                        'debit': aml.amount_residual < 0 and -aml.amount_residual or 0,
                        'credit': aml.amount_residual > 0 and aml.amount_residual or 0,
                        'move_line': aml,
                })
        _logger.info("-------- %s %s "%(counterpart_aml_dicts, balance) )
        return True


    def getAnalyticTagIdsTransactions(self, concepto_transaccion, conreplace=""):
        ctx = {}
        AccountAnalytic = self.env["account.analytic.account"]
        Tag = self.env["account.analytic.tag"]

        analytic_id, tag_id, code = None, None, ""
        concepto = concepto_transaccion.replace(conreplace, "")
        c3 = concepto[0:3].zfill(4)
        c2 = concepto[0:2].zfill(4)
        c1 = concepto[0:1].zfill(4)
        if c3.isdigit():
            code = "L%s"%c3
        elif c2.isdigit():
            code = "L%s"%c2
        elif c1.isdigit():
            code = "L%s"%c1
        analytic_id = AccountAnalytic.search_read([("code", "=", code)], fields=["name"])
        tag_id = Tag.search_read([("code", "=", code)], fields=["name", "code"])
        if(analytic_id or tag_id):
            ctx = {
                "tag_id": tag_id and tag_id[0].get("id") or False,
                "analytic_id": analytic_id and analytic_id[0]["id"] or False,
                "import_etl": True
            }
        return ctx


    def process_bank_statement_etl_line(self):
        ids = self.ids
        threaded_calculation = threading.Thread(target=self._process_bank_statement_etl_line, args=(ids))
        threaded_calculation.start()
        return True

    def _process_bank_statement_etl_line(self, ids):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['account.bank.statement'].process_bank_statement_thread(use_new_cursor=self._cr.dbname, ids=ids)
            new_cr.close()
            return {}

    def process_bank_statement_thread(self, use_new_cursor=False, ids=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        for stmLine in  self.browse(ids):
            stmLine.getProcessBankStatementLine(limit=0, use_new_cursor=use_new_cursor)
            if use_new_cursor:
                cr.commit()

        if use_new_cursor:
            cr.commit()
            cr.close()

    def getProcessBankStatementLine(self, limit=0, use_new_cursor=False):
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        statementLines = self.env['account.bank.statement.line']
        Account = self.env["account.account"]
        LayoutLine = self.env['bank.statement.export.layout.line']
        AccountMoveLine = self.env['account.move.line']
        Afiliation = self.env["account.bank.afiliation"]
        AccountAnalytic = self.env["account.analytic.account"]
        Tag = self.env["account.analytic.tag"]
        Codes = self.env['account.code.bank.statement']
        self._end_balance()
        if use_new_cursor:
            cr.commit()
        codigo = {}
        for codes_id in Codes.search([('company_id', '=', self.company_id.id), ('journal_id', '=', self.journal_id.id)]):
            for code in codes_id.code_line_ids:
                codigo[ code.name ] = code.account_id and code.account_id.id or False
                # codigo[ code.name.ljust(3, " ") ] = code.account_id and code.account_id.id or False
        extra_code = []
        ctx = dict(self._context, force_price_include=False)
        len_line_ids = len(self.line_ids.filtered(lambda l: not l.journal_entry_ids))
        _logger.info("01 ----------- Start statement process of %s lines"%(len_line_ids))
        counter = 0
        ret = False
        milliseconds = limit * 60 * 1000
        milliseconds_now = millis()
        for indx, st_line in enumerate(self.line_ids.filtered(lambda l: not l.journal_entry_ids)):
            if st_line.journal_entry_ids:
                continue
            if limit != 0:
                milliseconds_now_02 = millis()
                milliseconds_tmp = (milliseconds_now_02 - milliseconds_now)
                if milliseconds_tmp >= milliseconds:
                    break
            transaccion = st_line.note.split("|")
            codigo_transaccion = transaccion and transaccion[0].strip() or ""
            concepto_transaccion = transaccion and transaccion[1].strip() or ""
            ref = st_line.ref
            if codigo_transaccion in ['T17'] and ref: 
                # ref = ref.replace('0000001','')
                ref = ref[7:]
                std_ids = statementLines.search_read(
                    [
                        ('statement_id', '=', self.id), 
                        ('name', '=', st_line.name), 
                        ('ref', '=', st_line.ref),
                        ('note', 'like', 'T22|')
                    ], ['name', 'ref', 'note', 'amount'])
                _logger.info("---------- std_ids %s "%(std_ids) )
                for std_id in std_ids:
                    if abs( std_id['amount'] ) == abs(st_line.amount):
                        ref = ''
            if codigo_transaccion in ['T22']:
                ref = ''
            _logger.info("-------- codigo_transaccion %s %s  "%(codigo_transaccion, ref) )
            folioOdoo = ref and ref[:10] or ''
            if codigo_transaccion in ['T06']:
                folioOdoo = ref[7:17]
            if codigo_transaccion in ["P14"]:
                folioOdoo = ref.replace('REF:', '').replace('CIE:1', '').replace('CIE:0', '').strip()
            account_id = False
            _logger.info("02 *********** COUNT: %s | Process Line %s/%s - CODE %s -%s"%(counter, indx, len_line_ids, codigo_transaccion, st_line.name))
            counter += 1
            # if counter > 1:
            #     break
            res = False
            for layoutline_id in LayoutLine.search_read([('name', '=', folioOdoo)], 
                    fields=['id', 'name', 'cuenta_cargo', 'cuenta_abono', 'motivo_pago', 'referencia_numerica', 
                            'layout_id', 'movel_line_ids', 'partner_id', 'importe']
                ):
                movel_line_ids = layoutline_id.get('movel_line_ids') and layoutline_id['movel_line_ids'] or []
                move_lines = AccountMoveLine.browse(movel_line_ids)
                line_residual = st_line.currency_id and st_line.amount_currency or st_line.amount
                line_currency = st_line.currency_id or st_line.journal_id.currency_id or st_line.company_id.currency_id
                amount_residual = move_lines and sum(aml.currency_id and aml.amount_residual_currency or aml.amount_residual for aml in move_lines)
                total_residual = amount_residual or 0.0
                balance = total_residual - line_residual
                open_balance_dicts = []
                counterpart_aml_dicts = []
                amount_total = abs(line_residual)
                payment_aml_rec = self.env['account.move.line']
                reconciliationModel = self.env['account.reconciliation.widget']
                _logger.info(" TEST: Move IDS %s - %s "%(move_lines, st_line.name) )
                reconcileWidget = False

                amount = 0
                for aml in move_lines:
                    if aml.full_reconcile_id:
                        continue
                    if aml.currency_id:
                        break
                    amount = aml.currency_id and aml.amount_residual_currency or aml.amount_residual
                    if round(amount_total, 2) < round(abs(amount), 2):
                        st_line_ids = st_line.ids
                        counterpart_aml_dicts.append({
                                'name': aml.name if aml.name != '/' else aml.move_id.name,
                                'credit': amount_total < 0 and -amount_total or 0,
                                'debit': amount_total > 0 and amount_total or 0,
                                'counterpart_aml_id': aml.id,
                                'move_line': aml.id
                        })
                        data = [{
                            'partner_id': aml.partner_id.id,
                            'counterpart_aml_dicts': counterpart_aml_dicts,
                            'payment_aml_ids': [],
                            'new_aml_dicts': [],
                            'move_line': False,
                        }]
                        reconcileWidget = True
                        res=True
                        reconciliationModel.process_bank_statement_line(st_line_ids, data)
                        _logger.info("03 ----------- Start Reconcile %s - %s - %s - %s -%s -%s "%(data, st_line.name, st_line_ids, amount, amount_total, balance))
                        break
                    elif round(amount_total, 2) >= round(abs(amount), 2):
                        amount_total -= abs(amount)
                        counterpart_aml_dicts.append({
                                'name': aml.name if aml.name != '/' else aml.move_id.name,
                                'debit': amount < 0 and -amount or 0,
                                'credit': amount > 0 and amount or 0,
                                'move_line': aml,
                        })
                    else:
                        counterpart_aml_dicts.append({
                                'name': aml.name if aml.name != '/' else aml.move_id.name,
                                'debit': balance < 0 and -balance or 0,
                                'credit': balance > 0 and balance or 0,
                                'move_line': aml,
                        })
                if reconcileWidget == False and len(counterpart_aml_dicts) > 0:
                    _logger.info("03 ----------- Start Reconcile %s - %s - %s - %s -%s -%s "%(counterpart_aml_dicts, st_line.name, payment_aml_rec, amount, amount_total, balance))
                    res = st_line.with_context(ctx).process_reconciliation(counterpart_aml_dicts, payment_aml_rec, open_balance_dicts)
                if use_new_cursor:
                    cr.commit()
                _logger.info("04 ----------- End Reconcile: %s - %s"%(res or '', st_line.name))
                if res:
                    break
            if res:
                _logger.info("------RES %s -%s "%(codigo_transaccion, res) )
                ret = True
                continue
            ctx = {}
            if (codigo_transaccion in codigo):
                # for account_id in Account.search_read([('code_alias', 'ilike', codigo[codigo_transaccion]), 
                #         ('company_id', '=', st_line.company_id.id)], fields=["name"]):
                #     st_line.account_id = account_id.get("id")
                st_line.account_id = codigo[codigo_transaccion]

                for afiliation_id in Afiliation.search_read([("name", "ilike", st_line.name)], fields=["name", "description"], limit=1):
                    for tag_id in Tag.search_read([("afiliation_id", "=", afiliation_id.get("id"))], fields=["name", "code"]):
                        analytic_id = AccountAnalytic.search([("code", "=", tag_id.get("code"))])
                        ctx = {
                            "tag_id": tag_id.get("id"),
                            "analytic_id": analytic_id and analytic_id.id or False,
                            "import_etl": True
                        }
                if not ctx and codigo_transaccion in ["Y01", "Y15"]:
                    ctx = self.getAnalyticTagIdsTransactions(concepto_transaccion, conreplace="CE662143")
                elif not ctx and codigo_transaccion in ["Y16"]:
                    ctx = self.getAnalyticTagIdsTransactions(concepto_transaccion, conreplace="CI")
                elif not ctx and codigo_transaccion in ["C72"]:
                    concepto_transaccion_tmp = st_line.ref
                    ctx = self.getAnalyticTagIdsTransactions(concepto_transaccion_tmp, conreplace="CI")
                elif not ctx and codigo_transaccion in ["W01"]:
                    if (st_line.ref.upper().find('EMPENO') >= 0) or (st_line.ref.upper().find('EXPREQ') >= 0):
                        concepto_transaccion_tmp = st_line.ref
                        ctx = self.getAnalyticTagIdsTransactions(concepto_transaccion_tmp, conreplace="CI")
                if not ctx:
                    ctx = { "import_etl": True }
                ret = True
                st_line.with_context(ctx).fast_counterpart_creation()
                _logger.info("05 ----------- Codigo/Cuenta: %s/%s - ACCID:%s - CTX:%s"%(codigo_transaccion, 
                    codigo[codigo_transaccion], codigo[codigo_transaccion], ctx))
                if use_new_cursor:
                    cr.commit()
            _logger.info("06 ----------- END LINE")

        if use_new_cursor:
            cr.commit()
            cr.close()

        return ret


# C72 -- Tomar de las referencias
# Y01|CE662143 + número de sucursal LXXXX
# Y15|CE662143 + número de sucursal LXXXX
# Y16| "CI" + número de sucursal 1, 2 o 3 dígit


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def _prepare_reconciliation_move_line(self, move, amount):
        res = super(AccountBankStatementLine, self)._prepare_reconciliation_move_line(move, amount)
        if self._context.get("import_etl"):
            res["analytic_tag_ids"] = [self._context.get("tag_id")] # [(6, 0, self._context.get("tag_id"))]
            res["analytic_account_id"] = self._context.get("analytic_id")
        return res

    @api.multi
    def _prepare_move_line_for_currency(self, aml_dict, date):
        self.ensure_one()
        res = super(AccountBankStatementLine, self)._prepare_move_line_for_currency(aml_dict, date)
        if self._context.get("import_etl"):
            aml_dict["analytic_tag_ids"] = [self._context.get("tag_id")] # [(6, 0, self._context.get("tag_id"))]
            aml_dict["analytic_account_id"] = self._context.get("analytic_id")
