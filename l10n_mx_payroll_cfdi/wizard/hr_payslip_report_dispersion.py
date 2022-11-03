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



#---------------------------------------
#  Dispersion de Nóminas
#---------------------------------------
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

#---------------------------------------
#  Dispersion de Nóminas Banorte
#---------------------------------------
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

#---------------------------------------
#  Dispersion de Nóminas BBVA
#---------------------------------------
class ReportBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvatxt'
    _description = 'Dispersion BBVA - BBVA'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.dispersion_bbva_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_BBVA_%s.txt'%( company_id.id or 'Dispersion_BBVA_BBVA' )

class ReportBBVAInterTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvaintertxt'
    _description = 'Dispersion BBVA - Inter'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_Inter_%s.txt'%( company_id.id or 'Dispersion_BBVA_Inter' )

class ReportPayslipBBVAHSBCBancoppelTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvahsbcbancoppeltxt'
    _description = 'Dispersion BBVA - HSBC Bancoppel'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_hsbcbancoppel()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_Inter_%s.txt'%( company_id.id or 'Dispersion_BBVA_Inter' )

class ReportPayslipBBVABanbajioBanorteBanamexTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.dispersionbbvabajiobanortebantxt'
    _description = 'Dispersion BBVA SIN Banbajio Banorte Banamex'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_banbajiobanortebanamex()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_Inter_%s.txt'%( company_id.id or 'Dispersion_BBVA_Inter' )

class ReportPayslipBBVAInterVennTxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.payslipdispersionbbvaintervenntxt'
    _description = 'Dispersion BBVA - Inter Venn'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_bbva_inter_venn_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_Venn_%s.txt'%( company_id.id or 'Dispersion_BBVA_Venn' )


class ReportPayslipBBVATxt(models.AbstractModel):
    _name = 'report.l10n_mx_payroll_cfdi.payslipdispersionbbvavenntxt'
    _description = 'Dispersion BBVA - Venn'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        body = objects.with_context(rechazo=True).dispersion_bbva_inter_venn_datas()
        txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_BBVA_Inter_Venn_%s.txt'%( company_id.id or 'Dispersion_BBVA_Inter_Venn' )


#---------------------------------------
#  Dispersion de Nóminas Banbajio
#---------------------------------------
class ReportPayslipBanbajioBanorteBanamexTxt(models.AbstractModel):
    _name = 'report.banbajiobanortebanamextxt'
    _description = 'Dispersion Banbajio a Banorte - Banamex'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_banbajio_inter_banorte_banamex_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_Banbajio_Inter_%s.txt'%( company_id.id or 'Dispersion_Banbajio_Inter' )


class ReportPayslipBanbajioBanbajioTxt(models.AbstractModel):
    _name = 'report.banbajiobanbajiotxt'
    _description = 'Dispersion Banbajio a Banbajio'
    _inherit = 'report.report_txt.abstract'

    def __init__(self, pool, cr):
        self.sheet_header = None

    def generate_txt_report(self, txtfile, data, objects):
        for obj in objects:
            body = obj.dispersion_banbajio_banbajio_datas()
            txtfile.write(b'%s'%body.encode('utf-8'))

    def generate_txt_reportname(self, objs):
        company_id = self.env.user.company_id
        return 'Dispersion_Banbajio_Banbajio_%s.txt'%( company_id.id or 'Dispersion_Banbajio_Banbajio' )
