# -*- coding: utf-8 -*-
import logging
import threading
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools, registry, SUPERUSER_ID
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.tools.misc import split_every
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

import unicodedata

_logger = logging.getLogger(__name__)

def remove_accents(s):
    def remove_accent1(c):
        return unicodedata.normalize('NFD', c)[0]
    return u''.join(map(remove_accent1, s))

class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    #---------------------------------------
    #  Dispersion Nominas Banorte FDB Venn
    #---------------------------------------
    def dispersion_banortefdbvenn_datas(self, payslip_ids=[]):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'fdbvenn')
            if p_ids:
                return p_ids.dispersion_bbva_inter_venn_datas(run_id)
        return ''

    #---------------------------------------
    #  Dispersion Nominas Banorte - Banorte
    #---------------------------------------
    @api.multi
    def dispersion_banorte_datas(self):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'banorte')
            if p_ids:
                return p_ids.dispersion_banorte_datas_datos( run_id )
        return ''

    #---------------------------------------
    #  Dispersion Nominas Banorte FDB Interbancarias
    #---------------------------------------
    @api.multi
    def dispersion_banorte_inter_datas(self):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'inter')
            if p_ids:
                return p_ids.dispersion_banorte_interbancarias_datas_datos( run_id )
        return ''

    #---------------------------------------
    #  Dispersion Nominas BBVA - BBVA
    #---------------------------------------
    @api.multi
    def dispersion_bbva_datas(self):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'bbva')
            if p_ids:
                _logger.info('---------- Layout BBVA %s '%( len(p_ids) ) )
                return p_ids.dispersion_bbva_datas_datos( run_id )
        return ''

    #---------------------------------------
    #  Dispersion Nominas BBVA - Inter
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_datas(self):
        for run_id in self:
            where = ['inter']
            contact_id = self.env.ref('__export__.res_company_21_dbddd78a', False)
            if contact_id:
                where = ['inter', 'banorte']
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina in where)
            if p_ids:
                _logger.info('---------- Layout BBVA Inter %s '%( len(p_ids) ) )
                return p_ids.dispersion_bbva_inter_datas( run_id )
        return ''

    #---------------------------------------
    #  Dispersion Nominas BBVA - Inter - Venn
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_venn_datas(self):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina == 'fdbvenn')
            if p_ids:
                _logger.info('---------- Layout BBVA Inter %s '%( len(p_ids) ) )
                return p_ids.dispersion_bbva_inter_venn_datas( run_id )
        return ''

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    #---------------------------------------
    #  Dispersion Nominas Banorte Interbancarios
    #---------------------------------------
    def dispersion_banorte_interbancarias_datas_datos(self, run_id=None):
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
        for slip in self: # .env['hr.payslip'].browse(payslip_ids):
            total = slip.get_salary_line_total('C99')
            if total <= 0:
                continue
            employee_id = slip.employee_id or False
            bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
            if not bank_account_id:
                continue
            bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
            if not bank_number:
                continue
            indx += 1
            bank_type = '01'
            if bank_number != '072':
                bank_type = '40'
            cuenta = bank_account_id and bank_account_id.acc_number or ''
            # cuenta = cuenta[ : len(cuenta) -1 ]
            # cuenta = cuenta[-10:]
            monto_banco += total
            pp_total = '%.2f'%(total)
            pp_total = str(pp_total).replace('.', '')

            _logger.info('---------- Nom: %s - %s - %s -%s  '%(slip.number, bank_type, cuenta, pp_total ))

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

    #---------------------------------------
    #  Dispersion Nominas Banorte
    #---------------------------------------
    def dispersion_banorte_datas_datos(self, run_id=None):
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
        for slip in self: # .env['hr.payslip'].browse(payslip_ids):
            total = slip.get_salary_line_total('C99')
            if total <= 0:
                continue
            employee_id = slip.employee_id or False
            bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
            if not bank_account_id:
                continue
            bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
            if not bank_number:
                continue
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

            _logger.info('---------- Nom: %s - %s - %s -%s  '%(slip.number, bank_type, cuenta, pp_total ))

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

    #---------------------------------------
    #  Dispersion Nominas BBVA
    #---------------------------------------
    def dispersion_bbva_datas_datos(self, run_id=None):
        res_banco = []
        indx = 1
        for slip in self:   # .env['hr.payslip'].browse(payslip_ids):
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
    #  Dispersion Nominas BBVA - Inter
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_datas(self, run_id=None):
        res_banco = []
        indx = 1
        # p_ids = self.filtered(lambda r: r.layout_nomina != 'inter' and r.state == 'done' and r.get_salary_line_total('C99') > 0 )
        for slip in self:
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

    #---------------------------------------
    #  Dispersion Nominas BBVA - Inter - Venn
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_venn_datas(self, run_id=None):
        res_banco = []
        indx = 1
        for slip in self:
            employee_id = slip.employee_id or False
            total = slip.get_salary_line_total('C99')
            if total <= 0:
                _logger.info('---- Dispersion BBVA Inter Venn NO total=0 %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                continue

            bank_account_id = employee_id.bank_account_id and slip.employee_id.bank_account_id or False
            if not bank_account_id:
                _logger.info('---- Dispersion BBVA Inter NO bank_account_id %s %s %s '%( slip.id, slip.number, employee_id.id ) )
                continue

            bank_number = bank_account_id and bank_account_id.bank_id.bic or ''
            pp_cuenta = bank_account_id and bank_account_id.acc_number or ''
            if not pp_cuenta:
                _logger.info('---- Dispersion BBVA Inter NO CUENTA%s %s %s '%( slip.id, slip.number, employee_id.id ) )
                continue

            pp_total = '%.2f'%(total)
            pp_cc = ''
            if slip.company_id.bbva_cuenta_emisora:
                pp_cc = slip.company_id.bbva_cuenta_emisora
            else:
                if slip.company_id.id == 1:
                    pp_cc = '000000000156096999'
                elif slip.company_id.id == 2:
                    pp_cc = '000000000194219546'

            pp_nombre = '%s %s %s'%( employee_id.cfdi_appat, employee_id.cfdi_apmat, employee_id.name )
            pp_nombre = remove_accents(pp_nombre[:30])
            pp_noina = 'Nomina %s'%( slip.payslip_run_id and slip.payslip_run_id.name[:30] or slip.name[:30] )
            pp_noina = pp_noina[:30]

            pp_ref = '%s'%( slip.number.replace('SLIP/', '') )

            # bbva
            _logger.info('---------- layout_nomina %s '%( slip.layout_nomina ) )
            if slip.layout_nomina != 'bbva':
                res_banco.append((
                    'PSC',
                    '%s'%( pp_cuenta.rjust(18, "0") ),
                    pp_cc,
                    'MXP',
                    pp_total.rjust(16, "0"),
                    '%s'%( pp_nombre.ljust(30, " ") ),
                    '40',
                    '%s'%( bank_number ),
                    '%s'%( remove_accents(pp_noina).ljust(30, " ") ),
                    pp_ref.rjust(7, "0"),
                    'H'
                ))
            else:
                res_banco.append((
                    'PTC',
                    '%s'%( pp_cuenta.rjust(18, "0") ),
                    pp_cc,
                    'MXP',
                    pp_total.rjust(16, "0"),
                    '%s'%( remove_accents(pp_noina).ljust(30, " ") )
                ))
            indx += 1

        banco_datas = self._save_txt(res_banco)
        return banco_datas

    def _save_txt(self, data):
        file_value = ''
        for items in data:
            file_row = ''
            for indx, item in enumerate(items):
                file_row += u'%s'%item
            file_value += file_row + '\r\n'
        return file_value

class ReportBanorteFdbVennTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionfdbvenntxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_banortefdbvenn_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return ' FDBVenn%s.PAG'%( company_id.clave_emisora or 'DispersionBanorte.txt' )

class ReportBanorteTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbanortetxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_banorte_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return '%s.PAG'%( company_id.clave_emisora or 'DispersionBanorte.txt' )

class ReportBanorteInterTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbanorteintertxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_banorte_inter_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return '%s.PAG'%( company_id.clave_emisora or 'DispersionBanorte.txt' )

class ReportBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvatxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_bbva_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

class ReportBBVAInterTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvaintertxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

class ReportPayslipBBVAInterVennTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.payslipdispersionbbvaintervenntxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_venn_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'DispersionBBVA_Venn_%s.txt'%( company_id.id or 'DispersionBBVA_Venn' )


class ReportPayslipBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.payslipdispersionbbvavenntxt'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        # print('---- objects', objects)
        # objs = objects.filtered(lambda r: r.layout_nomina == 'inter')
        body = objects.with_context(rechazo=True).dispersion_bbva_inter_venn_datas()
        # body = obj.dispersion_bbva_inter_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'DispersionBBVA_Inter_%s.txt'%( company_id.id or 'DispersionBanorte' )
