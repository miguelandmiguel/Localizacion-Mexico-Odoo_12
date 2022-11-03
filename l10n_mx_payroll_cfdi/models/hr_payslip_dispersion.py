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

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    #---------------------------------------
    #  Dispersion Nominas Banorte Interbancarios
    #---------------------------------------
    def dispersion_banbajio(self, run_id=None):
        def get_header(acc_id):
            encabezado = "010000001030S900"
            encabezado += "{:.7}".format( (acc_id.grupo_afinidad or "").rjust(7, "0") )
            encabezado += "{:.8}".format( str(run_id.cfdi_date_payment).replace('-', '') )
            encabezado += "{:.20}".format( acc_id.acc_number.rjust(20, "0") )
            encabezado += "{:.130}".format( " ".rjust(130, " ") )
            encabezado += "\r\n"
            return encabezado

        def get_body(acc_id, indx=0, line=None):
            total = line.get_salary_line_total('C99')
            if total <= 0:
                return ""        
            acc_number = line.employee_id.bank_account_id and line.employee_id.bank_account_id.acc_number or ""
            detalle = "02"
            detalle += "{:.7}".format( str(indx or "").rjust(7, "0") )
            detalle += "90"
            detalle += "{:.8}".format( str(run_id.cfdi_date_payment).replace('-', '') )
            detalle += "000"
            detalle += "030"
            detalle += "{:.15}".format( str(total).replace(".", "").rjust(15, "0") )
            detalle += "{:.8}".format( str(run_id.cfdi_date_payment).replace('-', '') )
            detalle += "00{:.20} ".format( acc_id.acc_number.rjust(20, "0") )
            detalle += "00{:.20} ".format( str(acc_number or "").rjust(20, "0") )
            detalle += "{:.7}".format( str(indx or "").rjust(7, "0") )
            detalle += "{:.40}".format( remove_accents(line.name).ljust(40, " ") )
            detalle += "{:.30}".format("0".rjust(30, "0") )
            detalle += "{:.10}".format("0".rjust(10, "0") )
            detalle += "\r\n"
            return detalle

        def get_footer(indx, total):
            sumario = "09"
            sumario += "{:.7}".format( str(indx or 0).rjust(7, "0") )
            sumario += "90"
            sumario += "{:.7}".format( str(indx-1 or 0).rjust(7, "0") )
            sumario += "{:.18}".format( str(total).replace(".", "").rjust(18, "0") )
            sumario += "{:.145}".format( " ".rjust(145, " ") )
            sumario += "\r\n"
            return sumario

        Bank = self.env['res.partner.bank']
        partner_id = run_id.company_id.partner_id.commercial_partner_id
        bank_id = self.env['res.bank'].search([('bic', '=', '030')], limit=1)
        acc_id = Bank.search([('partner_id', '=', partner_id.id), ('bank_id', '=', bank_id.id)], limit=1)

        encabezado = get_header(acc_id)
        detalles = ""
        indx = 2
        total = 0.0
        for line in self:
            detalle = get_body(acc_id, indx, line)
            if detalle:
                detalles += detalle
                total += line.get_salary_line_total('C99')
                indx += 1
        sumario = get_footer(indx, total)
        banco_datas = encabezado + detalles + sumario
        return banco_datas

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
