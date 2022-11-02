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
    #  Dispersion Nominas BBVA - Inter HSBC Bancoppel
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_hsbcbancoppel(self):
        for run_id in self:
            where = ['hsbc', 'bancoppel']
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina in where)
            if p_ids:
                _logger.info('---------- Layout BBVA Inter HSBC Bancoppel %s '%( len(p_ids) ) )
                return p_ids.dispersion_bbva_inter_datas( run_id )
        return ''

    #---------------------------------------
    #  Dispersion Nominas BBVA - Inter SIN BANBAJIO-BANORTE-BANAMEX
    #---------------------------------------
    @api.multi
    def dispersion_bbva_inter_banbajiobanortebanamex(self):
        for run_id in self:
            where = ['bbva', 'banbajio', 'banorte', 'banamex']
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina not in where)
            if p_ids:
                _logger.info('---------- Layout BBVA Inter SIN SIN BANBAJIO-BANORTE-BANAMEX %s '%( len(p_ids) ) )
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


    #---------------------------------------
    #  Dispersion Nominas Banbajio - Inter - Banorte-Banamex
    #---------------------------------------
    @api.multi
    def dispersion_banbajio_inter_banorte_banamex_datas(self):
        for run_id in self:
            p_ids = run_id.slip_ids.filtered(lambda r: r.layout_nomina in ['banorte', 'banamex'])
            if p_ids:
                _logger.info('---------- Layout BBVA Inter %s '%( len(p_ids) ) )
                return p_ids.dispersion_banbajio_inter_banorte_banamex_datas( run_id )
        return ''
