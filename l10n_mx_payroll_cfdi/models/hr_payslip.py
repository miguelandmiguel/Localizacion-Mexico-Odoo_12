# -*- coding: utf-8 -*-

import base64
from itertools import groupby
import re
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO
import requests
from pytz import timezone
import pprint
from lxml import etree
from lxml.objectify import fromstring
from suds.client import Client
from suds.plugin import MessagePlugin
import pprint
import logging

from odoo import _, api, fields, models, tools, registry
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.tools.float_utils import float_repr
from odoo.tools.misc import split_every
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError
from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

import threading

_logger = logging.getLogger(__name__)

CATALOGO_TIPONOMINA = [('O','Ordinaria'), ('E','Extraordinaria')]

class LogPlugin(MessagePlugin):
    def pretty_log(self, xml_content):
        try:
            tree = fromstring( '%s'%xml_content )
            xml = etree.tostring(tree, xml_declaration=True, encoding='UTF-8')
            _logger.info( '%s'%xml )
        except:
            _logger.info( '%s'%xml_content)

    def sending(self, context):
        self.pretty_log( '%s'%context.envelope )
    def received(self, context):
        self.pretty_log( '%s'%context.reply)

CFDI_TEMPLATE_33 = 'l10n_mx_payroll_cfdi.cfdipayslipv33'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/3.3/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi/data/xslt/3.3/cadenaoriginal_TFD_1_1.xslt'

def create_list_html(array):
    '''Convert an array of string to a html list.
    :param array: A list of strings
    :return: an empty string if not array, an html list otherwise.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'

def getAntiguedad(date_from, date_to):
    FechaInicioRelLaboral = datetime.strptime(date_from, "%Y-%m-%d")
    FechaFinalPago = datetime.strptime(date_to, "%Y-%m-%d")
    FechaFinalPago = FechaFinalPago +relativedelta(days=+0)
    difference = relativedelta(FechaFinalPago, FechaInicioRelLaboral)

    years = difference.years
    months = difference.months
    days = difference.days

    logging.info("years %s "%years )
    logging.info("months %s "%months )
    logging.info("days %s "%days )

    p_diff = "P"
    if years > 0:
        p_diff += "%sY"%(years)
    if months > 0:
        p_diff += "%sM"%(months)
    if days > 0 or days==0:
        p_diff += "%sD"%(days)
    return p_diff

class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'
    _description = 'Generate payslips for all selected employees'

    def _get_available_contracts_domain(self):
        return [('contract_id.state', 'in', ('open', 'close')), ('company_id', '=', self.env.user.company_id.id)]

    def _get_employees(self):
        # YTI check dates too
        return self.env['hr.employee'].search(self._get_available_contracts_domain())

    employee_ids = fields.Many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees',
                                    default=lambda self: self._get_employees(), required=True)

    @api.model
    def _run_compute_sheet_tasks(self, use_new_cursor=False, active_id=False, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME

            payslipModel = self.env['hr.payslip']
            payslips = []
            for employees_chunk in split_every(20, employee_ids):
                for employee in self.env['hr.employee'].browse(employees_chunk):
                    _logger.info('--- Nomina Procesando Employees %s', employees_chunk )
                    slip_data = self.env['hr.payslip'].onchange_employee_id(from_date, to_date, employee.id, contract_id=False)
                    res = {
                        'employee_id': employee.id,
                        'name': slip_data['value'].get('name'),
                        'struct_id': slip_data['value'].get('struct_id'),
                        'contract_id': slip_data['value'].get('contract_id'),
                        'payslip_run_id': active_id,
                        'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                        'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                        'date_from': from_date,
                        'date_to': to_date,
                        'credit_note': credit_note,
                        'company_id': employee.company_id.id,
                    }
                    payslip_id = self.env['hr.payslip'].create(res)
                    payslips.append(payslip_id.id)
                    if use_new_cursor:
                        self._cr.commit()
            _logger.info('--- Nomina payslips %s ', len(payslips) )
            for slip_chunk in split_every(5, payslips):
                _logger.info('--- Nomina payslip_ids %s ', slip_chunk )
                try:
                    payslipModel.with_context(slip_chunk=True).browse(slip_chunk).compute_sheet()
                    if use_new_cursor:
                        self._cr.commit()
                except:
                    pass
            if use_new_cursor:
                self._cr.commit()

        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _compute_sheet_threading(self, active_id, from_date=False, to_date=False, credit_note=False, employee_ids=[]):
        with api.Environment.manage():
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            self.env['hr.payslip.employees']._run_compute_sheet_tasks(
                use_new_cursor=self._cr.dbname,
                active_id=active_id, from_date=from_date, to_date=to_date, credit_note=credit_note, employee_ids=employee_ids)
            new_cr.close()
            return {}

    @api.multi
    def compute_sheet(self):
        [data] = self.read()
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        threaded_calculation = threading.Thread(target=self._compute_sheet_threading, args=( active_id, from_date, to_date, run_data.get('credit_note'), data['employee_ids'] ))
        threaded_calculation.start()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def compute_sheet_old(self):
        payslips = self.env['hr.payslip']
        [data] = self.read()
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(['date_start', 'date_end', 'credit_note'])
        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        for employee in self.env['hr.employee'].browse(data['employee_ids']):
            slip_data = self.env['hr.payslip'].onchange_employee_id(from_date, to_date, employee.id, contract_id=False)
            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': slip_data['value'].get('contract_id'),
                'payslip_run_id': active_id,
                'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                'date_from': from_date,
                'date_to': to_date,
                'credit_note': run_data.get('credit_note'),
                'company_id': employee.company_id.id,
                'cfdi_source_sncf': slip_data['value'].get('cfdi_source_sncf'),
                'cfdi_amount_sncf': slip_data['value'].get('cfdi_amount_sncf'),
                'cfdi_tipo_nomina': slip_data['value'].get('cfdi_tipo_nomina'),
                'cfdi_tipo_nomina_especial': slip_data['value'].get('cfdi_tipo_nomina_especial')
            }
            payslips += self.env['hr.payslip'].create(res)
        payslips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'l10n_mx_edi.pac.sw.mixin', 'mail.thread']

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('none', 'CFDI not necessary'),
            ('retry', 'Retry'),
            ('to_sign', 'To sign'),
            ('signed', 'Signed'),
            ('to_cancel', 'To cancel'),
            ('cancelled', 'Cancelled')
        ],
        string='PAC status', default='none',
        help='Refers to the status of the CFDI inside the PAC.',
        readonly=True, copy=False)
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'State not defined'),
            ('undefined', 'Not Synced Yet'),
            ('not_found', 'Not Found'),
            ('cancelled', 'Cancelled'),
            ('valid', 'Valid'),
        ],
        string='SAT status',
        help='Refers to the status of the CFDI inside the SAT system.',
        readonly=True, copy=False, required=True,
        track_visibility='onchange', default='undefined')
    l10n_mx_edi_cfdi_name = fields.Char(string='CFDI name', copy=False, readonly=True,
        help='The attachment name of the CFDI.')
    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Way',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Indicates the way the payment was/will be received, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc.')
    l10n_mx_edi_cfdi = fields.Binary(
        string='Cfdi content', copy=False, readonly=True,
        help='The cfdi xml content encoded in base64.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_uuid = fields.Char(string='Fiscal Folio', copy=False, readonly=True,
        help='Folio in electronic invoice, is returned by SAT when send to stamp.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_certificate_id = fields.Many2one('l10n_mx_edi.certificate',
        string='Certificate', copy=False, readonly=True,
        help='The certificate used during the generation of the cfdi.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('Supplier RFC', copy=False, readonly=True,
        help='The supplier tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('Customer RFC', copy=False, readonly=True,
        help='The customer tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origin', copy=False,
        help='In some cases the payment must be regenerated to fix data in it. '
        'In that cases is necessary this field filled, the format is: '
        '\n04|UUID1, UUID2, ...., UUIDn.\n'
        'Example:\n"04|89966ACC-0F5C-447D-AEF3-3EED22E711EE,89966ACC-0F5C-447D-AEF3-3EED22E711EE"')

    date_invoice = fields.Date(string='Invoice Date',
        readonly=False, states={'draft': [('readonly', False)]}, index=True,
        help="Keep empty to use the current date", copy=False)
    cfdi_timeinvoice = fields.Char(
        string='Time invoice', readonly=False, copy=False,
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the current México central time")

    cfdi_es_sncf = fields.Boolean(string='Entidad SNCF')
    cfdi_source_sncf = fields.Selection([
            ('', ''),
            ('IP', 'Ingresos propios'),
            ('IF', 'Ingreso federales'),
            ('IM', 'Ingresos mixtos')],
        string="Recurso Entidad SNCF", oldname="source_sncf")
    cfdi_amount_sncf = fields.Monetary(string="Monto Recurso SNCF", oldname="amount_sncf", default=False)
    cfdi_monto = fields.Monetary(string="Monto CFDI", copy=False, oldname="monto_cfdi")
    cfdi_total = fields.Float(string="Total", copy=False, compute='_compute_total_payslip', oldname="total")

    @api.one
    @api.depends('line_ids', 'line_ids.code')
    def _compute_total_payslip(self):
        self.cfdi_total = self.get_salary_line_total('C99')


    @api.one
    @api.depends('l10n_mx_edi_cfdi_name')
    def _compute_cfdi_values(self):
        """Fill the invoice fields from the cfdi values."""
        for rec in self:
            attachment_id = rec.l10n_mx_edi_retrieve_last_attachment()
            if not attachment_id:
                continue
            attachment_id = attachment_id[0]
            # At this moment, the attachment contains the file size in its 'datas' field because
            # to save some memory, the attachment will store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname)
            if not datas:
                _logger.exception('The CFDI attachment cannot be found')
                continue
            rec.l10n_mx_edi_cfdi = datas
            tree = rec.l10n_mx_edi_get_xml_etree(base64.decodestring(datas))
            tfd_node = rec.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                rec.l10n_mx_edi_cfdi_uuid = tfd_node.get('UUID')

            rec.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get(
                'Rfc', tree.Emisor.get('rfc'))
            rec.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get(
                'Rfc', tree.Receptor.get('rfc'))
            certificate = tree.get('noCertificado', tree.get('NoCertificado'))
            rec.l10n_mx_edi_cfdi_certificate_id = self.env['l10n_mx_edi.certificate'].sudo().search(
                [('serial_number', '=', certificate)], limit=1)

    # YTI TODO To rename. This method is not really an onchange, as it is not in any view
    # employee_id and contract_id could be browse records
    @api.multi
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        res = super(HrPayslip, self).onchange_employee_id(date_from=date_from, date_to=date_to, employee_id=employee_id, contract_id=contract_id)
        model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if model == 'hr.payslip.run':
            payslip_run_id = self.env[model].browse(active_id)
            cfdi_tipo_nomina = 'O' if payslip_run_id.cfdi_tipo_nomina_especial == 'ord' else 'E'
            res['value'].update({
                "cfdi_source_sncf": payslip_run_id.cfdi_source_sncf,
                "cfdi_amount_sncf": payslip_run_id.cfdi_amount_sncf,
                "cfdi_tipo_nomina": cfdi_tipo_nomina,
                "cfdi_tipo_nomina_especial": payslip_run_id.cfdi_tipo_nomina_especial
            })
            struct = payslip_run_id.struct_id
            if not struct:
                return res
            res['value'].update({
                'struct_id': struct.id,
            })
        return res

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        #get the xslt path
        xslt_path = CFDI_XSLT_CADENA_TFD
        #get the cfdi as eTree
        cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        #return the cadena
        return self.l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        '''Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information contained within the cfdi.
        This can be encoded with the certificate to create the digital seal.
        Since the cadena is generated with the invoice data, any change in it will be noticed resulting in a different
        cadena and so, ensure the invoice has not been modified.

        :param xslt_path: The path to the xslt file.
        :param cfdi_as_tree: The cfdi converted as a tree
        :return: A string computed with the invoice data called the cadena
        '''
        res = tools.file_open(xslt_path)
        xslt_root = etree.parse(res)
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))        

    def getDatasXmlPayslip(self):
        RegimenModel = self.env['l10n_mx_payroll.regimen_contratacion']
        RiesgoModel = self.env['l10n_mx_payroll.riesgo_puesto']
        JornadaModel = self.env['l10n_mx_payroll.tipojornada']
        PeriodicidadModel = self.env['l10n_mx_payroll.periodicidad_pago']
        TypeModel = self.env['hr.contract.type']

        self._compute_cfdi_values()
        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        if not attachment_id:
            return {}

        cfdi = self.l10n_mx_edi_get_xml_etree()
        cfdi = cfdi if cfdi is not None else {}
        Emisor = cfdi.Emisor
        Nomina = self.l10n_mx_edi_get_nomina12_etree(cfdi)
        tfd = self.l10n_mx_edi_get_tfd_etree(cfdi)

        if not cfdi:
            return {
                'Serie': ''
            }

        nodo_p = self._get_agrupadorsat_type('p')
        nodo_d = self._get_agrupadorsat_type('d')
        nodo_o = self._get_agrupadorsat_type('o')

        Total = float(cfdi.get('Total', '0.0'))
        res = {
            'Serie': cfdi.get('Serie'),
            'Folio': cfdi.get('Folio'),
            'LugarExpedicion': cfdi.get('LugarExpedicion'),
            'MetodoPago': u'PUE - Pago en una sola exhibición',
            'Fecha': cfdi.get('Fecha'),
            'FormaPago': '99 - Por definir',
            'NoCertificado': cfdi.get('NoCertificado'),
            'EmisorRfc': Emisor.get('Rfc'),
            'SubTotal': float(cfdi.get('SubTotal', '0.0')),
            'Total': Total,
            'Descuento': float(cfdi.get('Descuento', '0.0')),
            'CadenaOriginal': self._get_l10n_mx_edi_cadena(),
            'Sello': cfdi.get('Sello')[-8:],
            'SelloSAT': tfd.get('SelloSAT'),
            'SelloCFDI': tfd.get('SelloCFD'),
            'UUID':tfd.get('UUID'),
            'FechaTimbrado': tfd.get('FechaTimbrado'),
            'AmountText': self.l10n_mx_edi_amount_to_text( Total )
        }
        if Nomina is not None:
            NomEmisor = None
            NomReceptor = None
            Percepciones = {
                'TotalSueldos': 0.0,
                'TotalGravado': 0.0,
                'TotalExento': 0.0,
                'Lines': []
            }
            Deducciones = {
                'TotalOtrasDeducciones': 0.0,
                'TotalImpuestosRetenidos': 0.0,
                'TotalImporte': 0.0,
                'Lines': []
            }
            OtrosPagos = []
            OrigenRecurso, MontoRecursoPropio = '', ''
            Incapacidad = 0.0
            for nom in Nomina:
                NomReceptor = nom.Receptor
                NomEmisor = nom.Emisor
                origen = nom.Emisor.find('EntidadSNCF')
                if origen is not None:
                    OrigenRecurso = origen.get('OrigenRecurso')
                    MontoRecursoPropio = origen.get('MontoRecursoPropio')
                Percepciones = {
                    'TotalSueldos': float(nom.Percepciones.get('TotalSueldos', 0.0)),
                    'TotalGravado': float(nom.Percepciones.get('TotalGravado', 0.0)),
                    'TotalExento': float(nom.Percepciones.get('TotalExento', 0.0)),
                    'Lines': []
                }
                pindx = 0
                for perc in nom.Percepciones.Percepcion:
                    pindx += 1
                    psat = nodo_p.get( perc.get('TipoPercepcion') )
                    TipoPercepcion = '[%s] %s'%( psat.get('code'), psat.get('name')  )
                    perc_tmp = {
                        'indx': pindx,
                        'Clave': perc.get('Clave'),
                        'Concepto': perc.get('Concepto'),
                        'ImporteExento': float(perc.get('ImporteExento', 0.0)),
                        'ImporteGravado': float(perc.get('ImporteGravado', 0.0)),
                        'TipoPercepcion': TipoPercepcion
                    }
                    Percepciones['Lines'].append(perc_tmp)
                Deducciones = {
                    'TotalOtrasDeducciones': float(nom.Deducciones.get('TotalOtrasDeducciones', 0.0)),
                    'TotalImpuestosRetenidos': float(nom.Deducciones.get('TotalImpuestosRetenidos', 0.0)),
                    'TotalImporte': 0.0,
                    'Lines': []
                }
                for deduc in nom.Deducciones.Deduccion:
                    dsat = nodo_d.get( deduc.get('TipoDeduccion') )
                    TipoDeduccion = '[%s] %s'%( dsat.get('code'), dsat.get('name')  )
                    Deducciones['TotalImporte'] += float(deduc.get('Importe'))
                    deduc_tmp = {
                        'TipoDeduccion': TipoDeduccion,
                        'Clave': deduc.get('Clave'),
                        'Concepto': deduc.get('Concepto'),
                        'Importe': float(deduc.get('Importe')),
                    }
                    Deducciones['Lines'].append(deduc_tmp)
                OtrosPagos = []
                if nom.OtrosPagos is not None:
                    oindx = 0
                    for otro in nom.OtrosPagos.OtroPago:
                        oindx += 1
                        osat = nodo_o.get( otro.get('TipoOtroPago') )
                        TipoOtroPago = '[%s] %s'%( osat.get('code'), osat.get('name')  )
                        OtrosPagos.append({
                            'Clave': otro.get('Clave'),
                            'Concepto': otro.get('Concepto'),
                            'Importe': float(otro.get('Importe')),
                            'TipoOtroPago': TipoOtroPago,
                            'indx': oindx
                        })
                inca = nom.find('Incapacidad')
                if inca is not None:
                    Incapacidad = inca.get('ImporteMonetario')
                break
            TipoRegimen = NomReceptor.get('TipoRegimen')
            if TipoRegimen is not None:
                reg = RegimenModel.search([('code', '=', TipoRegimen)], limit=1)
                TipoRegimen = '[%s] %s'%( reg.code, reg.name )

            RiesgoPuesto = NomReceptor.get('RiesgoPuesto')
            if RiesgoPuesto is not None:
                riesgo = RiesgoModel.search([('code', '=', RiesgoPuesto)], limit=1)
                RiesgoPuesto = '[%s] %s'%( riesgo.code, riesgo.name )

            TipoContrato = NomReceptor.get('TipoContrato')
            if TipoContrato is not None:
                tipo = TypeModel.search([('code', '=', TipoContrato)], limit=1)
                TipoContrato = '[%s] %s'%( tipo.code, tipo.name )

            TipoJornada = NomReceptor.get('TipoJornada')
            if TipoContrato is not None:
                jornada = JornadaModel.search([('code', '=', TipoJornada)], limit=1)
                TipoJornada = '[%s] %s'%( jornada.code, jornada.name )

            PeriodicidadPago = NomReceptor.get('PeriodicidadPago')
            if PeriodicidadPago is not None:
                periodo = PeriodicidadModel.search([('code', '=', PeriodicidadPago)], limit=1)
                PeriodicidadPago = '[%s] %s'%( periodo.code, periodo.name )
            TipoNomina = Nomina.get('TipoNomina')
            resNomina = {
                'RegistroPatronal': NomEmisor.get('RegistroPatronal'),
                'RfcPatronOrigen': NomEmisor.get('RfcPatronOrigen'),
                'OrigenRecurso': OrigenRecurso,

                'MontoRecursoPropio': MontoRecursoPropio,
                'ReceptorCurp': NomReceptor.get('Curp', ''),
                'NumEmpleado': NomReceptor.get('NumEmpleado'),
                'TipoRegimen': TipoRegimen,
                'Departamento': NomReceptor.get('Departamento'),
                'Puesto': NomReceptor.get('Puesto'),
                'RiesgoPuesto': RiesgoPuesto,
                'TipoContrato': TipoContrato,
                'Sindicalizado': NomReceptor.get('Sindicalizado'),
                'TipoJornada': TipoJornada,
                'Antiguedad': NomReceptor.get('Antigüedad'),
                'FechaInicioRelLaboral': NomReceptor.get('FechaInicioRelLaboral'),
                'F': NomReceptor.get('SalarioDiarioIntegrado'),
                'ClaveEntFed': NomReceptor.get('ClaveEntFed'),
                'PeriodicidadPago': PeriodicidadPago,
                'SalarioBaseCotApor': NomReceptor.get('SalarioBaseCotApor'),
                'NumSeguridadSocial': NomReceptor.get('NumSeguridadSocial'),
                'CuentaBancaria': NomReceptor.get('CuentaBancaria'),
                'Banco': NomReceptor.get('Banco'),
                
                'FechaPago': Nomina.get('FechaPago'),
                'FechaInicialPago': Nomina.get('FechaInicialPago'),
                'FechaFinalPago': Nomina.get('FechaFinalPago'),
                'TotalPercepciones': Nomina.get('TotalPercepciones'),
                'TotalDeducciones': Nomina.get('TotalDeducciones'),
                'TotalOtrosPagos': Nomina.get('TotalOtrosPagos'),
                'NumDiasPagados': Nomina.get('NumDiasPagados'),
                'TipoNomina': u'Nómina Ordinaria' if TipoNomina == 'O' else u'Nómina ExtraOrdinaria',
                'Percepciones': Percepciones,
                'Deducciones': Deducciones,
                'OtrosPagos': OtrosPagos,
                'Incapacidad': Incapacidad
            }
            res.update(resNomina)
        _logger.info('------report_payslip_params:\n%s', pprint.pformat(res))
        return res

    @api.multi
    def l10n_mx_edi_amount_to_text(self, amount_total):
        """Method to transform a float amount to text words
        E.g. 100 - ONE HUNDRED
        :returns: Amount transformed to words mexican format for invoices
        :rtype: str
        """
        self.ensure_one()
        currency = self.currency_id.name.upper()
        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = 'M.N' if currency == 'MXN' else 'M.E.'
        # Split integer and decimal part
        amount_i, amount_d = divmod(amount_total, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))
        words = self.currency_id.with_context(lang='es_ES').amount_to_text(amount_i).upper()
        invoice_words = '%(words)s %(amount_d)02d/100 %(curr_t)s' % dict(
            words=words, amount_d=amount_d, curr_t=currency_type)
        return invoice_words

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        """Retrieve all the cfdi attachments generated for this payment.

        :return: An ir.attachment recordset
        """
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_name:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', 'like', self.l10n_mx_edi_cfdi_name )
        ]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids and attachment_ids[0] or None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        '''Get an objectified tree representing the cfdi.
        If the cfdi is not specified, retrieve it from the attachment.

        :param cfdi: The cfdi as string
        :return: An objectified tree
        '''
        #TODO helper which is not of too much help and should be removed
        self.ensure_one()
        if cfdi is None:
            cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        res = fromstring(cfdi)
        return res

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        '''Get the TimbreFiscalDigital node from the cfdi.
        :param cfdi: The cfdi as etree
        :return: the TimbreFiscalDigital node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_nomina12_etree(self, cfdi):
        '''Get the TimbreFiscalDigital node from the cfdi.
        :param cfdi: The cfdi as etree
        :return: the TimbreFiscalDigital node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'nomina12:Nomina[1]'
        namespace = {'nomina12': 'http://www.sat.gob.mx/nomina12'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payment_etree(self, cfdi):
        '''Get the Complement node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the Payment node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node
    
    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        '''Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information contained within the cfdi.
        This can be encoded with the certificate to create the digital seal.
        Since the cadena is generated with the invoice data, any change in it will be noticed resulting in a different
        cadena and so, ensure the invoice has not been modified.

        :param xslt_path: The path to the xslt file.
        :param cfdi_as_tree: The cfdi converted as a tree
        :return: A string computed with the invoice data called the cadena
        '''
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.multi
    def action_date_assign(self):
        self.ensure_one()
        date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
        if not self.date_invoice:
            self.date_invoice = date_mx.date()
        if not self.cfdi_timeinvoice:
            self.cfdi_timeinvoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)
        return True

    @api.multi
    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        """Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :param code: an eventual error code
        :param msg: an eventual error msg
        """
        # TODO - Duplicated
        self.ensure_one()
        if xml_signed:
            body_msg = _('The sign service has been called with success')
            # Update the pac status
            self.l10n_mx_edi_pac_status = 'signed'
            self.l10n_mx_edi_cfdi = xml_signed
            # Update the content of the attachment
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            attachment_id.write({
                'datas': xml_signed,
                'mimetype': 'application/xml'
            })
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg))

    @api.multi
    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message)

    @api.multi
    def _l10n_mx_edi_finkok_sign(self, pac_info):
        """SIGN for Finkok."""
        # TODO - Duplicated with the invoice one
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        _logger.info('--- Username  %s %s '%(username, password) )
        res = {}
        for rec in self:
            extra = False
            cfdi = [rec.l10n_mx_edi_cfdi.decode('UTF-8')]
            # _logger.info('---- CFDI %s '%cfdi )
            try:
                client = Client(url, cache=None, timeout=80, plugins=[LogPlugin()])
                response = client.service.stamp(cfdi, username, password)
                _logger.info('-- _nomina_cfdi-reques: Values received:\n%s', pprint.pformat(response))
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                return {'error': str(e)}
                continue
            code = 0
            msg = None
            xml_signed = getattr(response, 'xml', None)
            if response.Incidencias:
                code = getattr(response.Incidencias[0][0], 'CodigoError', None)
                msg = getattr(response.Incidencias[0][0], 'MensajeIncidencia', None)
                extra = getattr(response.Incidencias[0][0], 'ExtraInfo', None)
                if extra:
                    msg += '  %s'%extra
                rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)
                body_msg = _('The sign service requested failed')
                self.message_post(
                    body=body_msg + create_list_html([msg]))
                return {
                    'error': msg
                }
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)
        return res


    @run_after_commit
    @api.one
    def _l10n_mx_edi_call_service(self, service_type):
        """Call the right method according to the pac_na
        me, it's info returned
        by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel"""
        invoice_obj = self.env['account.invoice']
        pac_name = self.company_id.l10n_mx_edi_pac
        pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
        service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
        pac_info = getattr(self, pac_info_func)(self.company_id, service_type)
        return getattr(self, service_func)(pac_info)
    
    @api.one
    def _l10n_mx_edi_sign(self):
        '''Call the sign service with records that can be signed.
        '''
        if self.l10n_mx_edi_pac_status not in ['signed', 'to_cancel', 'cancelled', 'retry']:
            return self._l10n_mx_edi_call_service('sign')
        return {'error': 'No se puede timbrar'}

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        '''Returns the cfdi version to generate the CFDI.
        In December, 1, 2017 the CFDI 3.2 is deprecated, after of July 1, 2018
        the CFDI 3.3 could be used.
        '''
        version = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_cfdi_version', '3.3')
        return version

    @api.multi
    def _l10n_mx_edi_finkok_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        if service_type == 'sign':
            url = 'http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/stamp.wsdl'
        else:
            url = 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'cfdi@vauxoo.com' if test else username,
            'password': 'vAux00__' if test else password,
        }


    @staticmethod
    def _l10n_mx_get_serie_and_folio(number):
        values = {'serie': None, 'folio': None}
        number = (number or '').strip()
        number_matchs = [rn for rn in re.finditer('\d+', number)]
        if number_matchs:
            last_number_match = number_matchs[-1]
            values['serie'] = number[:last_number_match.start()] or None
            values['folio'] = last_number_match.group().lstrip('0') or None

        if values.get('serie'):
            values['serie'] = values['serie'].replace('/', '').replace('-', '').replace('_', '')
        return values

    def _get_days(self, code=""):
        dias = 0
        horas = 0
        if not self.worked_days_line_ids:
            return dias, horas
        for line in self.worked_days_line_ids:
            if line.code == code:
                dias = line.number_of_days
                horas = line.number_of_hours
                break
        return dias, horas

    @staticmethod
    def _get_string_cfdi(text, size=100):
        """Replace from text received the characters that are not found in the
        regex. This regex is taken from SAT documentation
        https://goo.gl/C9sKH6
        text: Text to remove extra characters
        size: Cut the string in size len
        Ex. 'Product ABC (small size)' - 'Product ABC small size'"""
        if not text:
            return None
        text = text.replace('|', ' ').replace('/', '').replace('-', '').replace('_', '')
        return text.strip()[:size]


    def _get_days(self, code):
        context = dict(self._context) or {}
        dias = 0
        horas = 0
        for line in self.worked_days_line_ids:
            if line.code == code:
                dias = line.number_of_days
                horas = line.number_of_hours
                break
        else:
            message = "<li>Error \n\nNo se encontro entrada de dias trabajados con codigo %s</li>"%code
            self.action_raisemessage(message)
        return dias, horas

    def _get_code(self, line):
        if not line.salary_rule_id.cfdi_codigoagrupador_id:
            message = "<li>Error \n\nNo tiene codigo SAT: %s</li>"%line.salary_rule_id.name
            self.action_raisemessage(message)
        codigo = line.salary_rule_id.cfdi_codigoagrupador_id.code
        nombre = line.salary_rule_id.cfdi_codigoagrupador_id.name
        return codigo, nombre

    def _get_lines_type(self, ttype):
        Model = self.env['ir.model.data']
        line_ids = self.line_ids
        tipos = {
            'p': Model.get_object("l10n_mx_payroll", "catalogo_tipo_percepcion").id,
            'd': Model.get_object("l10n_mx_payroll", "catalogo_tipo_deduccion").id,
            'h': Model.get_object("l10n_mx_payroll", "catalogo_tipo_hora_extra").id,
            'i': Model.get_object("l10n_mx_payroll", "catalogo_tipo_incapacidad").id,
            'o': Model.get_object("l10n_mx_payroll", "catalogo_tipo_otro_pago").id
        }
        # lines = self.line_ids.filtered(lambda r: r.salary_rule_id.cfdi_tipo_id.id == tipos[ttype] and r.salary_rule_id.cfdi_appears_onpayslipreport == True)
        lines = self.line_ids.filtered(lambda r: r.salary_rule_id.cfdi_tipo_id.id == tipos[ttype])
        return lines

    def _get_agrupadorsat_type(self, ttype):
        ModelAgrupador = self.env['l10n_mx_payroll.codigo_agrupador']
        Model = self.env['ir.model.data']
        tipos = {
            'p': Model.get_object("l10n_mx_payroll", "catalogo_tipo_percepcion").id,
            'd': Model.get_object("l10n_mx_payroll", "catalogo_tipo_deduccion").id,
            'h': Model.get_object("l10n_mx_payroll", "catalogo_tipo_hora_extra").id,
            'i': Model.get_object("l10n_mx_payroll", "catalogo_tipo_incapacidad").id,
            'o': Model.get_object("l10n_mx_payroll", "catalogo_tipo_otro_pago").id
        }
        res = {}
        for agrup in ModelAgrupador.search([('cfdi_tipo_id', '=', tipos[ttype])]):
            res[ agrup.code ] = {
                'name': agrup.name,
                'code': agrup.code,
                'id': agrup.id
            }
        return res

    @api.multi
    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if self.l10n_mx_edi_origin == False:
            return {}
        origin = self.l10n_mx_edi_origin.split('|')
        uuids = origin[1].split(',') if len(origin) > 1 else []
        return {
            'type': origin[0],
            'related': [u.strip() for u in uuids],
        }

    def getEntidadSNCF(self):
        EntidadSNCF = None
        if self.cfdi_source_sncf:
            EntidadSNCF = {
                'OrigenRecurso': self.cfdi_source_sncf
            }
            if self.cfdi_amount_sncf != 0.0:
                EntidadSNCF['MontoRecursoPropio'] = self.cfdi_amount_sncf
            return EntidadSNCF

    def getPercepciones(self):
        empleado = self.employee_id
        totalPercepciones = 0.0
        totalGravadoP = 0.0
        totalExentoP = 0.0
        totalSueldosP = 0.0
        totalSepIndem = 0.0
        totalJubilacion = 0.0
        percepciones = None
        nodo_p = self._get_lines_type('p')
        if nodo_p:
            percepciones = {
                'totalPercepciones': 0.0,
                'lines': [],
                'attrs': {
                    'TotalGravado': 0.0,
                    'TotalExento': 0.0,
                    'TotalSueldos': 0.0,
                }
            }
            for percepcion in nodo_p:
                tipo_percepcion, nombre_percepcion = self._get_code(percepcion)
                tipo = percepcion.salary_rule_id.cfdi_gravado_o_exento or 'gravado'
                gravado = percepcion.total if tipo == 'gravado' else 0
                exento = percepcion.total if tipo == 'exento' else 0
                if gravado + exento == 0:
                    continue
                nombre_percepcion = percepcion.name or ''
                nodo_percepcion = {
                    'TipoPercepcion': tipo_percepcion,
                    'Clave': percepcion.code,
                    'Concepto': nombre_percepcion.replace(".", "").replace("/", ""),
                    'ImporteGravado': "%.2f"%gravado,
                    'ImporteExento': "%.2f"%exento
                }
                totalGravadoP += gravado
                totalExentoP += exento
                if tipo_percepcion not in ("022", "023", "025", "039", "044"):
                    totalSueldosP += gravado + exento
                elif tipo_percepcion in ("022", "023", "025"):
                    totalSepIndem += gravado + exento
                elif tipo_percepcion in ("039", "044"):
                    totalJubilacion += gravado + exento

                horas_extras = None
                if tipo_percepcion == '019':
                    tipo_horas = "01" #percepcion.salary_rule_id.tipo_horas.code or "01"
                    days_code = "EXTRA2" if tipo_horas == '01' else 'EXTRA3'
                    dias, horas = self._get_days(percepcion, days_code)
                    horas_extras = {
                        'Dias': "%d"%dias,
                        'TipoHoras': "%s"%tipo_horas,
                        'HorasExtra': "%d"%horas,
                        'ImportePagado': "%.2f"%(gravado + exento),
                    }
                acciones_titulos = None

                percepciones['lines'].append({
                    'attrs': nodo_percepcion,
                    'horas_extras': horas_extras,
                    'acciones_titulos': acciones_titulos
                })
            percepciones['attrs']['TotalGravado'] = "%.2f"%totalGravadoP
            percepciones['attrs']['TotalExento'] = "%.2f"%totalExentoP
            percepciones['attrs']['TotalSueldos'] = "%.2f"%totalSueldosP
            totalPercepciones = totalSueldosP + totalSepIndem + totalJubilacion
            percepciones['totalPercepciones'] = totalSueldosP + totalSepIndem + totalJubilacion

            if totalSepIndem:
                #-------------------
                # Nodo indemnización
                #-------------------
                ultimo_sueldo_mensual = empleado.cfdi_sueldo_imss * 30
                percepciones["SeparacionIndemnizacion"] = {
                    'TotalPagado': "%.2f"%totalSepIndem,
                    'NumAniosServicio': empleado.cfdi_anos_servicio,
                    'UltimoSueldoMensOrd': ultimo_sueldo_mensual,
                    'IngresoAcumulable': "%.2f"%min(totalSepIndem, ultimo_sueldo_mensual),
                    'IngresoNoAcumulable': "%.2f"%totalSepIndem - ultimo_sueldo_mensual
                }
                percepciones["attrs"]["TotalSeparacionIndemnizacion"] = "%.2f"%totalSepIndem

            if totalJubilacion:
                ultimo_sueldo_mensual = empleado.cfdi_sueldo_imss * 30
                #-------------------
                # Nodo Jubilación
                #-------------------
                vals = {
                   'TotalUnaExhibición': "%.2f"%totalJubilacion,
                   'IngresoAcumulable': "%.2f"%min(totalJubilacion, ultimo_sueldo_mensual),
                   'IngresoNoAcumulable': "%.2f"%totalJubilacion - ultimo_sueldo_mensual
                }
                # Si es en parcialidades
                if tipo_percepcion == '044': 
                   del vals['TotalUnaExhibición'],
                   vals.update({
                      'TotalParcialidad': "%.2f"%totalJubilacion,
                      'MontoDiario': "%.2f"%empleado.cfdi_retiro_paricialidad
                   })
                percepciones["JubilacionPensionRetiro"] = vals
                percepciones["attrs"]["TotalJubilacionPensionRetiro"] = "%.2f"%totalJubilacion
        # TotalSeparacionIndemnizacion
        return percepciones

    def getDeducciones(self):
        totalDeducciones = 0.0
        totalD = 0.0
        retenido = 0.0
        deducciones = None
        nodo_d = self._get_lines_type('d')
        if nodo_d:
            lines_d = []
            attrs_d = {}
            for deduccion in nodo_d:
                tipo_deduccion, nombre_deduccion = self._get_code(deduccion)
                if tipo_deduccion == '002':
                    retenido += deduccion.total
                else:
                    totalD += deduccion.total
                if deduccion.total == 0:
                    continue
                nombre_deduccion = deduccion.name or ''
                nodo_deduccion = {
                    'TipoDeduccion': tipo_deduccion,
                    'Clave': deduccion.code,
                    'Concepto': nombre_deduccion.replace(".", "").replace("/", "").replace("(", "").replace(")", ""),
                    'Importe': "%.2f"%abs(deduccion.total),
                }
                lines_d.append(nodo_deduccion)
            
            if totalD != 0.00:
                attrs_d['TotalOtrasDeducciones'] = "%.2f"%abs(totalD)
            if retenido != 0.00:
                attrs_d['TotalImpuestosRetenidos'] = "%.2f"%abs(retenido)
            # deducciones["attrs"]["TotalImpuestosRetenidos"] = "%.2f"%retenido
            if (lines_d and attrs_d):
                totalDeducciones = totalD + retenido
                deducciones = {
                    'totalDeducciones': abs(totalD + retenido),
                    'lines': lines_d,
                    'attrs': attrs_d
                }
        return deducciones

    def getOtrosPagos(self):
        tz = self.env.user.tz
        TipoRegimen = self.contract_id.cfdi_regimencontratacion_id and self.contract_id.cfdi_regimencontratacion_id.code or False
        fecha_utc =  datetime.now(timezone("UTC"))
        fecha_local = fecha_utc.astimezone(timezone(tz)).strftime("%Y-%m-%dT%H:%M:%S")

        totalOtrosPagos = 0.0
        nodo_o = self._get_lines_type('o')
        otros_pagos = None
        if nodo_o:
            otros_pagos = {
                'lines': [],
                'totalOtrosPagos': 0.0
            }
            for otro_pago in nodo_o:
                if otro_pago.total == 0.0:
                    continue
                tipo_otro_pago, nombre_otro_pago = self._get_code(otro_pago)
                nombre_otro_pago = otro_pago.name or ''
                attrs = {
                    'TipoOtroPago': tipo_otro_pago,
                    'Clave': otro_pago.code,
                    'Concepto': nombre_otro_pago.replace(".", "").replace("/", "").replace("(", "").replace(")", ""),
                    'Importe': "%.2f"%abs(otro_pago.total)
                }
                totalOtrosPagos += otro_pago.total
                #--------------------
                # Subsidio al empleo
                #--------------------
                SubsidioAlEmpleo = None
                CompensacionSaldosAFavor = None
                if tipo_otro_pago == '002':
                    SubsidioAlEmpleo = {
                        'SubsidioCausado': "%.2f"%abs(otro_pago.total)
                    }
                #--------------------
                # Compensación anual
                #--------------------
                elif tipo_otro_pago == '004':
                   year = int(fecha_local.split("-")[0])
                   CompensacionSaldosAFavor = {
                       'SaldoAFavor': "%.2f"%abs(otro_pago.total),
                       'Año': "%s"%(year-1),
                       'RemanenteSalFav': 0
                   }
                otros_pagos['lines'].append({
                    'attrs': attrs,
                    'SubsidioAlEmpleo': SubsidioAlEmpleo,
                    'CompensacionSaldosAFavor': CompensacionSaldosAFavor,
                    'totalOtrosPagos': totalOtrosPagos
                })
        if otros_pagos:
            otros_pagos['totalOtrosPagos'] = totalOtrosPagos

        if TipoRegimen == '02' and otros_pagos == None:
            tipo_otro_pago = '002'
            nombre_otro_pago = 'Subsidio para el empleo'
            otros_pagos = {
                'lines': [{
                    'attrs': {
                        'TipoOtroPago': tipo_otro_pago,
                        'Clave': tipo_otro_pago,
                        'Concepto': nombre_otro_pago.replace(".", "").replace("/", "").replace("(", "").replace(")", ""),
                        'Importe': "%.2f"%abs(0.0)
                    },
                    'SubsidioAlEmpleo': {
                        'SubsidioCausado': "%.2f"%abs(0.0)
                    }
                }]
            }
        return otros_pagos

    def getIncapacidades(self):
        nodo_i = self._get_lines_type('i')
        incapacidades = None
        if nodo_i:
            incapacidades = []
            for incapacidad in nodo_i:
                inca = self._get_input(incapacidad)
                if inca != 0:
                    tipo_incapacidad, nombre_incapacidad = self._get_code(incapacidad)
                    nodo_incapacidad = {
                        "DiasIncapacidad": "%d"%self._get_input(incapacidad),
                        "TipoIncapacidad": tipo_incapacidad,
                        "ImporteMonetario": "%.2f"%abs(incapacidad.total),
                    }
                    incapacidades.append(nodo_incapacidad)
                    
        return incapacidades


    def _get_SalarioBaseCotApor(self):
        _logger.info('---------- Table exists %s '%( tools.table_exists(self._cr, 'x_hr_employee_wage') ) )
        if tools.table_exists(self._cr, 'x_hr_employee_wage'):
            wage_id = self.env['x_hr_employee_wage'].sudo().search([('x_employee_id','=', self.employee_id.id), ('x_state','=','actual')])
            if wage_id:
                return wage_id.x_cfdi_sueldo_diario or 0.0
            else:
                return 0.0
        else:
            return self.employee_id.cfdi_sueldo_diario and '%.2f'%self.employee_id.cfdi_sueldo_diario or None

    @api.multi
    def _l10n_mx_edi_create_cfdi_values(self):
        self.ensure_one()
        empleado = self.employee_id
        company = self.company_id
        fecha_alta = empleado.cfdi_date_start or self.contract_id.date_start or False
        antiguedad = getAntiguedad('%s'%fecha_alta, '%s'%self.date_to)
        RiesgoPuesto = empleado.job_id and empleado.job_id.cfdi_riesgopuesto_id and empleado.job_id.cfdi_riesgopuesto_id.code or False
        periodicidad_pago = self.contract_id.cfdi_periodicidadpago_id and self.contract_id.cfdi_periodicidadpago_id.code or ""
        banco = False
        num_cuenta = False
        if empleado.bank_account_id:
            banco = empleado.bank_account_id and empleado.bank_account_id.bank_id.bic or ''
            nocuenta = empleado.bank_account_id and empleado.bank_account_id.acc_number or ''
            num_cuenta = nocuenta[len(nocuenta)-16:]

        AccionesOTitulos = None
        HorasExtra = None

        EntidadSNCF = self.getEntidadSNCF()
        Percepciones = self.getPercepciones() if (self.getPercepciones() and self.getPercepciones()['lines']) else {}
        JubilacionPensionRetiro = Percepciones.get('JubilacionPensionRetiro')
        SeparacionIndemnizacion = Percepciones.get('SeparacionIndemnizacion')
        Deducciones = self.getDeducciones()
        OtrosPagos = self.getOtrosPagos()
        Incapacidades = self.getIncapacidades()

        TotalPercepciones = Percepciones and abs(float(Percepciones.get('totalPercepciones', '0.0'))) or 0.0
        TotalDeducciones = Deducciones and abs(float(Deducciones.get('totalDeducciones', '0.0'))) or 0.0
        TotalOtrosPagos = OtrosPagos and abs(float(OtrosPagos.get('totalOtrosPagos', '0.0'))) or 0.0
        importe = (TotalPercepciones or 0.0) + (TotalOtrosPagos or 0.0)
        subtotal = importe
        descuento = TotalDeducciones or 0.0
        total = subtotal - descuento
        values = {
            'record': self,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'fiscal_position': self.company_id.partner_id.property_account_position_id,
            'issued': self.journal_id.l10n_mx_address_issued_id,
            'customer': self.employee_id,
            'NumDiasPagados': "%d"%self._get_days("WORK100")[0],
            "RegistroPatronal": company.cfdi_registropatronal_id and company.cfdi_registropatronal_id.name or False,
            'antiguedad': antiguedad,
            'fecha_alta': fecha_alta,
            'RiesgoPuesto': RiesgoPuesto,
            'periodicidad_pago': periodicidad_pago,
            'banco': banco,
            'num_cuenta': num_cuenta,
            'TotalPercepciones': "%.2f"%TotalPercepciones,
            'TotalDeducciones': "%.2f"%TotalDeducciones,
            'TotalOtrosPagos': "%.2f"%TotalOtrosPagos if TotalOtrosPagos != None else None,
            'EntidadSNCF': EntidadSNCF,
            'Percepciones': Percepciones or None,
            'JubilacionPensionRetiro': JubilacionPensionRetiro,
            'SeparacionIndemnizacion': SeparacionIndemnizacion,
            'Deducciones': Deducciones,
            'OtrosPagos': OtrosPagos,
            'Incapacidades': Incapacidades,
            'importe': "%.2f"%importe,
            'descuento': "%.2f"%descuento,
            'subtotal': "%.2f"%subtotal,
            'total': "%.2f"%total,
            'amount_total': 1.0,
            'amount_untaxed': 1.0,
            'valor_unitario': 1.0
        }
        values.update(self._l10n_mx_get_serie_and_folio(self.number))
        partner = self.journal_id.l10n_mx_address_issued_id or self.company_id.partner_id.commercial_partner_id
        tz = self.env['account.invoice']._l10n_mx_edi_get_timezone(partner.state_id.code)
        date_mx = datetime.now(tz)
        time_invoice = date_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.date_invoice),
            datetime.strptime(time_invoice, '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        return values

    @api.multi
    def l10n_mx_edi_create_cfdi(self):
        self.ensure_one()
        self.action_date_assign()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()
        _logger.info('--- Values %s '%values )
        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]
        cfdi = qweb.render(CFDI_TEMPLATE_33, values=values)
        cfdi = cfdi.replace(b'xmlns__', b'xmlns:')
        cfdi = b' '.join(cfdi.split())
        node_sello = 'Sello'
        attachment = self.env.ref('l10n_mx_edi.xsd_cached_cfdv33_xsd', False)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b''
        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA, tree)
        tree.attrib[node_sello] = certificate_id.sudo().get_encrypted_cadena(cadena)
        # Check with xsd

        xmlDatas = etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        # _logger.info('------------------xmlDatas %s '%xmlDatas )
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (IOError, ValueError):
                _logger.info(
                    _('The xsd file to validate the XML structure was not found'))
            except Exception as e:
                return {'error': (_('The cfdi generated is not valid') +
                                    create_list_html(str(e).split('\\n')))}
        return {'cfdi': etree.tostring(tree, xml_declaration=True, encoding='UTF-8')}
        # return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    @api.multi
    def l10n_mx_edi_update_pac_status(self):
        '''Synchronize both systems: Odoo & PAC if the invoices need to be signed or cancelled.
        '''
        for record in self:
            if record.l10n_mx_edi_pac_status in ('to_sign', 'retry'):
                record.l10n_mx_edi_retry()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()

    @api.multi
    def action_payslip_cfdivalues(self):
        self.ensure_one()
        post_msg = []
        body_msg = _('Error: Validacion XML')
        fechaAlta = self.employee_id.cfdi_date_start or self.employee_id.contract_id.date_start or False
        riesgoPuesto = self.employee_id.job_id and self.employee_id.job_id.cfdi_riesgopuesto_id and self.employee_id.job_id.cfdi_riesgopuesto_id.code or False
        salarioDiarioIntegrado = self.employee_id.cfdi_sueldo_diario and '%.2f'%self.employee_id.cfdi_sueldo_diario or False
        tipoContrato = self.contract_id.type_id and self.contract_id.type_id.code or ''
        periodicidadPago = self.contract_id.cfdi_periodicidadpago_id and self.contract_id.cfdi_periodicidadpago_id.code or ''
        tipoRegimen = self.contract_id.cfdi_regimencontratacion_id and self.contract_id.cfdi_regimencontratacion_id.code or ''
        res = False
        if not self.employee_id.cfdi_rfc:
            post_msg.extend([_('El Empleado no tiene "RFC" ')])
        if not tipoContrato:
            post_msg.extend([_('El Empleado no tiene "Tipo Contrato" ')])
        if not periodicidadPago:
            post_msg.extend([_('El Empleado no tiene "Periodicidad Pago" ')])
        if not tipoRegimen:
            post_msg.extend([_('El Empleado no tiene "Tipo Regimen" ')])
        if not self.employee_id.cfdi_imss:
            post_msg.extend([_('El Empleado no tiene "No. IMSS" ')])
        if not fechaAlta:
            post_msg.extend([_('El Empleado no tiene "Fecha Alta"')])
        if not riesgoPuesto:
            post_msg.extend([_('El Empleado no tiene "Riesgo Puesto" ')])
        if not salarioDiarioIntegrado:
            post_msg.extend([_('El Empleado no tiene "Salario Diario Integrado" ')])
        if post_msg:
            self.message_post(body=body_msg + create_list_html(post_msg))
            res = True
        return res

    @api.multi
    def l10n_mx_edi_retry(self):
        '''Try to generate the cfdi attachment and then, sign it.
        '''
        self.ensure_one()
        res = self.action_payslip_cfdivalues()
        if res:
            return {}
        version = self.l10n_mx_edi_get_pac_version()
        for payslip in self:
            number = payslip.number.replace('SLIP','').replace('/','')
            cfdi_values = payslip.l10n_mx_edi_create_cfdi()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                _logger.info('Error %s '%error )
                # cfdi failed to be generated
                payslip.l10n_mx_edi_pac_status = 'retry'
                payslip.message_post(body=error, subtype='account.mt_invoice_validated')
                return {'error': error}
            payslip.l10n_mx_edi_pac_status = 'to_sign'
            filename = ('%s-%s-MX-Payslip-%s.xml' % (
                payslip.journal_id.code, number, version.replace('.', '-'))).replace('/', '')
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            payslip.l10n_mx_edi_cfdi_name = filename

            # Guarda XML
            attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                'name': filename,
                'res_id': payslip.id,
                'res_model': payslip._name,
                'datas': base64.encodestring(cfdi),
                'datas_fname': filename,
                'description': 'Mexican Payslip',
                })
            payslip.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id],
                subtype='account.mt_invoice_validated')
            cfdi_values = payslip._l10n_mx_edi_sign()
            payslip.action_payslip_print_report()
        return {}

    @api.multi
    def action_payslip_print_report(self):
        for payslip in self:
            # Guarda PDF
            try:
                if not payslip.struct_id or not payslip.struct_id.report_id:
                    report = self.env.ref('hr_payroll.action_report_payslip', False)
                else:
                    report = payslip.struct_id.report_id
                    aa = report.render_qweb_pdf(payslip.id)
                pdf_content, content_type = report.render_qweb_pdf(payslip.id)
                if payslip.struct_id.report_id.print_report_name:
                    pdf_name = safe_eval(payslip.struct_id.report_id.print_report_name, {'object': payslip})
                else:
                    pdf_name = _("Payslip")
            except Exception as e:
                payslip.message_post(body='Error al imprimir : %s '%(e)  )
        return True

    @api.multi
    def action_payslip_done(self):
        error = None
        res = self.action_payslip_cfdivalues()
        if res:
            return False
        res = super(HrPayslip, self).action_payslip_done()
        for rec in self:
            if rec.contract_id.is_cfdi:
                version = self.l10n_mx_edi_get_pac_version()
                number = rec.number.replace('SLIP','').replace('/','')
                rec.l10n_mx_edi_cfdi_name = ('%s-%s-MX-Payslip-%s.xml' % (
                    rec.journal_id.code, number, version.replace('.', '-'))).replace('/', '')
                result = rec.l10n_mx_edi_retry()
                if result.get('error'):
                    return result

        return res

    @api.one
    def action_payslip_cancel_nomina(self):
        if self.state == 'draft':
            self.cancel = 'cancel'
        if not self.l10n_mx_edi_cfdi_name:
            self.move_id.reverse_moves()
            self.state = 'cancel'
            return True
        # Manda Cancelar
        message = ''
        res = self.cancel()
        if res:
            self.state = 'cancel'
            self.move_id.reverse_moves()


    @api.multi
    def cancel(self):
        result = False
        # for record in self.filtered(lambda r: r.l10n_mx_edi_pac_status in ['to_sign', 'signed', 'to_cancel']):
        for record in self:
            result = record._l10n_mx_edi_cancel()
        return result

    @api.one
    def _l10n_mx_edi_cancel(self):
        for record in self:
            return record._l10n_mx_edi_call_service('cancel')

    @api.one
    def _l10n_mx_edi_finkok_cancel(self, pac_info):
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuid = inv.l10n_mx_edi_cfdi_uuid
            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            company_id = self.company_id
            cer_pem = base64.encodestring(certificate_id.get_pem_cer(
                certificate_id.content)).decode('UTF-8')
            key_pem = base64.encodestring(certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)).decode('UTF-8')
            cancelled = False
            code = False
            acuse = ''
            try:
                client = Client(url, timeout=20)
                invoices_list = client.factory.create("UUIDS")
                invoices_list.uuids.string = [uuid]
                response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem.replace(
                    '\n', ''), key_pem)
                _logger.info('-- _nomina_cfdi-reques: Cancel received:\n%s', pprint.pformat(response))

            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                return False
            if not hasattr(response, 'Folios'):
                msg = _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios[0][0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
                xmlacuse = response.Acuse
                xmlacuse = xmlacuse[xmlacuse.find("<CancelaCFDResponse"):xmlacuse.find("</s:Body>")]
                xmlacuse = xmlacuse.replace('<CancelaCFDResponse "', '<CancelaCFDResponse xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance " ')
                acuse = xmlacuse
            return inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg, acuse)

    @api.multi
    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None, acuse=None):
        '''Post process the results of the cancel service.
        :param cancelled: is the cancel has been done with success
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''
        self.ensure_one()
        if cancelled:
            body_msg = _('The cancel service has been called with success')
            self.l10n_mx_edi_pac_status = 'cancelled'
            if acuse:
                base64_str = base64.encodestring(('%s'%(acuse)).encode()).decode().strip()
                ctx = self.env.context.copy()
                ctx.pop('default_type', False)
                filename = "cancelacion_cfd_%s.xml"%(self.number.replace('/', '') or "")
                attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                    'name': filename,
                    'res_id': self.id,
                    'res_model': self._name,
                    'datas': base64_str,
                    'datas_fname': filename,
                    'description': 'Cancel Mexican Payslip',
                    })
                self.message_post(
                    body=_('Cancel CFDI document'),
                    attachment_ids=[attachment_id.id],
                    subtype='account.mt_invoice_validated')

        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg))
        return cancelled

    @api.multi
    def send_nomina(self):
        self.ensure_one()
        template = self.env.ref('l10n_mx_payroll_cfdi.email_template_payroll', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict()
        ctx.update({
            'default_model': 'hr.payslip',
            'default_res_id': self.id,
            'default_use_template': bool(template),
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
        })
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

# http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/GuiaNomina11102019.pdf
