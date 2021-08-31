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

from odoo import _, api, fields, models, tools, registry
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.tools.float_utils import float_repr
from odoo.tools.misc import split_every
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError
from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit
import unicodedata
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

def remove_accents(s):
    def remove_accent1(c):
        return unicodedata.normalize('NFD', c)[0]
    return u''.join(map(remove_accent1, s))

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


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'l10n_mx_edi.pac.sw.mixin', 'mail.thread']

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, 
        track_visibility='onchange', default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""")
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
        track_visibility='onchange', 
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
    l10n_mx_edi_sendemail = fields.Boolean(string="Send Email", default=False)
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
    cfdi_total = fields.Float(string="Total", copy=False, oldname="total")

    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string='Departamento', store=True, readonly=True)

    # l10n_mx_cfdi_uuid = fields.Char(string='Folio Fiscal')
    #--------------------
    # Layout Dispersion
    #--------------------
    layout_nomina = fields.Selection([
            ('fdbvenn', ' FDB Venn'),
            ('banorte', 'Banorte'),
            ('bbva', 'BBVA Bancomer'),
            ('inter', 'Interbancarios'),
            ('efectivo', 'Efectivo')
        ], string='Dispersion Nomina', default='efectivo', compute='_compute_dispersionnomina')


    @api.multi
    def _compute_dispersionnomina(self):
        for payslip in self:
            layout_nomina = 'efectivo'
            bic = payslip.employee_id.bank_account_id and payslip.employee_id.bank_account_id.bank_id and payslip.employee_id.bank_account_id.bank_id.bic or False
            if not bic:
                payslip.layout_nomina = layout_nomina
                continue

            if bic == '012':
                layout_nomina = 'bbva'
            elif bic == '072':
                layout_nomina = 'banorte'
            elif bic == '151':
                layout_nomina = 'fdbvenn'                
            else:
                layout_nomina = 'inter'

            """
            if bic == '012':
                layout_nomina = 'bbva'
            else:
                if payslip.company_id.sin_dispersion_banorte:
                    layout_nomina = 'bbva_inter'
                else:
                    if bic == '072':
                        layout_nomina = 'banorte'
                    elif bic not in ['012', '072']:
                        layout_nomina = 'bbva_inter'
            """
            if bic == '151':
                _logger.info('------ layout_nomina %s %s - '%(payslip.number, layout_nomina) )
            payslip.layout_nomina = layout_nomina

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
    # Static Method
    # -------------------------------------------------------------------------
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

    @staticmethod
    def _get_string_cfdi(text, size=100):
        if not text:
            return None
        text = text.replace('|', ' ').replace('/', '').replace('-', '').replace('_', '')
        return text.strip()[:size]

    @staticmethod
    def _getRemoverAcentos(remover=''):
        return remove_accents( remover )

    @staticmethod
    def _getMayusculas(palabras=''):
        return palabras.upper()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        lines = super(HrPayslip, self)._get_payslip_lines(contract_ids, payslip_id)

        context = dict(self.env.context)
        cfdi_nomina = context.get('cfdi_nomina', {})
        ruleModel = self.env['hr.salary.rule']
        fields = ['cfdi_tipo_id', 'cfdi_tipohoras_id', 'cfdi_gravado_o_exento', 'cfdi_codigoagrupador_id', 'cfdi_agrupacion_id', 'cfdi_tipo_neg_id', 'cfdi_tipohoras_neg_id', 'cfdi_gravado_o_exento_neg', 'cfdi_codigoagrupador_neg_id', 'cfdi_agrupacion_neg_id']
        for line in lines:
            rule_ids = ruleModel.search_read([('id', '=', line.get('salary_rule_id'))], fields)
            total =  float(line.get('quantity', 0.0)) * line.get('amount', 0.0) * line.get('rate', 0.0) / 100
            if total >= 0:
                for rule_id in rule_ids:
                    totales = cfdi_nomina.get( rule_id['id'], {} )
                    line['total_exento'] = totales.get('total_exento', 0.0)
                    line['total_gravado'] = totales.get('total_gravado', 0.0)

                    line['cfdi_tipo_id'] = rule_id.get('cfdi_tipo_id') and rule_id['cfdi_tipo_id'][0] or False
                    line['cfdi_tipohoras_id'] = rule_id.get('cfdi_tipohoras_id') and rule_id['cfdi_tipohoras_id'][0] or False
                    line['cfdi_gravado_o_exento'] = rule_id.get('cfdi_gravado_o_exento')  or False
                    line['cfdi_codigoagrupador_id'] = rule_id.get('cfdi_codigoagrupador_id') and rule_id['cfdi_codigoagrupador_id'][0] or False
                    line['cfdi_agrupacion_id'] = rule_id.get('cfdi_agrupacion_id') and rule_id['cfdi_agrupacion_id'][0] or False
            elif total < 0:
                for rule_id in rule_ids:
                    totales = cfdi_nomina.get( rule_id['id'], {} )
                    line['total_exento'] = totales.get('total_exento', 0.0)
                    line['total_gravado'] = totales.get('total_gravado', 0.0)

                    line['cfdi_tipo_id'] = rule_id.get('cfdi_tipo_neg_id') and rule_id['cfdi_tipo_neg_id'][0] or False
                    line['cfdi_tipohoras_id'] = rule_id.get('cfdi_tipohoras_neg_id') and rule_id['cfdi_tipohoras_neg_id'][0] or False
                    line['cfdi_gravado_o_exento'] = rule_id.get('cfdi_gravado_o_exento_neg') or False
                    line['cfdi_codigoagrupador_id'] = rule_id.get('cfdi_codigoagrupador_neg_id') and rule_id['cfdi_codigoagrupador_neg_id'][0] or False
                    line['cfdi_agrupacion_id'] = rule_id.get('cfdi_agrupacion_neg_id') and rule_id['cfdi_agrupacion_neg_id'] or False
        return lines

    @api.model
    def _get_company_name(self):
        cia_name = self.company_id.partner_id.name
        nombre = self._getRemoverAcentos(cia_name)
        return self._getMayusculas( nombre )

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        xslt_path = CFDI_XSLT_CADENA_TFD
        cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        return self.l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        res = tools.file_open(xslt_path)
        xslt_root = etree.parse(res)
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))        

    @api.model
    def l10n_mx_edi_amount_to_text(self, amount_total):
        self.ensure_one()
        currency = self.currency_id.name.upper()
        currency_type = 'M.N' if currency == 'MXN' else 'M.E.'
        amount_i, amount_d = divmod(amount_total, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))
        words = self.currency_id.with_context(lang='es_ES').amount_to_text(amount_i).upper()
        invoice_words = '%(words)s %(amount_d)02d/100 %(curr_t)s' % dict(
            words=words, amount_d=amount_d, curr_t=currency_type)
        return invoice_words

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
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
        self.ensure_one()
        if cfdi is None:
            cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        res = fromstring(cfdi)
        return res

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_nomina12_etree(self, cfdi):
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'nomina12:Nomina[1]'
        namespace = {'nomina12': 'http://www.sat.gob.mx/nomina12'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payment_etree(self, cfdi):
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        version = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_cfdi_version', '3.3')
        return version

    @api.model
    def _get_days(self, code=""):
        dias, horas = 0, 0
        for line in self.worked_days_line_ids:
            if line.code == code:
                dias = line.number_of_days
                horas = line.number_of_hours
                break
        else:
            message = "<li>Error \n\nNo se encontro entrada de dias trabajados con codigo %s</li>"%code
            # self.action_raisemessage(message)
            self.message_post(body=_('%s') % message)
        return dias, horas

    @api.model
    def _get_input(self, line):
        regla = line.salary_rule_id
        codigo = ''
        cantidad = 0
        for inp in regla.input_ids:
            codigo = inp.code
            break
        for inp in self.input_line_ids:
            if inp.code == codigo:
                cantidad = inp.amount
                break
        return cantidad

    @api.model
    def _get_code(self, line):
        if not line.cfdi_codigoagrupador_id:
            message = "<li>Error \n\nNo tiene codigo SAT: %s</li>"%line.name
            # self.action_raisemessage(message)
            self.message_post(body=_('%s') % message)
        codigo = line.cfdi_codigoagrupador_id.code
        nombre = line.cfdi_codigoagrupador_id.name
        return codigo, nombre

    @api.model
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
        lines = self.line_ids.filtered(lambda r: r.cfdi_tipo_id.id == tipos[ttype] and r.cfdi_codigoagrupador_id.code != False )
        return lines

    @api.model
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

    @api.model
    def _get_lines_type_report(self, ttype):
        Model = self.env['ir.model.data']
        line_ids = self.line_ids
        tipos = {
            'p': Model.get_object("l10n_mx_payroll", "catalogo_tipo_percepcion").id,
            'd': Model.get_object("l10n_mx_payroll", "catalogo_tipo_deduccion").id,
            'h': Model.get_object("l10n_mx_payroll", "catalogo_tipo_hora_extra").id,
            'i': Model.get_object("l10n_mx_payroll", "catalogo_tipo_incapacidad").id,
            'o': Model.get_object("l10n_mx_payroll", "catalogo_tipo_otro_pago").id
        }
        lines = self.line_ids.filtered(lambda r: r.salary_rule_id.cfdi_tipo_id.id == tipos[ttype] and r.salary_rule_id.appears_on_payslip == True )
        return lines

    def getLinesPDFReport(self, ttype=''):
        res = {
            'Lines': [],
            'Importe': 0.0
        }
        for line in self._get_lines_type_report(ttype):
            if line.code == 'C109':
                continue
            if line.total == 0.0:
                continue
            line_tmp = {
                'id': line,
                'Clave': line.code,
                'Concepto': line.name,
                'Importe': line.total
            }
            res['Lines'].append( line_tmp )
            res['Importe'] += line.total
        return res
    
    # -------------------------------------------------------------------------
    # Datas for PDF reports
    # -------------------------------------------------------------------------
    @api.model
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
        Receptor = cfdi.Receptor
        Nomina = self.l10n_mx_edi_get_nomina12_etree(cfdi)
        tfd = self.l10n_mx_edi_get_tfd_etree(cfdi)
        if not cfdi:
            return {
                'Serie': ''
            }

        RegimenFiscal = Emisor.get('RegimenFiscal')
        if RegimenFiscal is not None:
            reg = self.env['account.fiscal.position'].search([('l10n_mx_edi_code', '=', RegimenFiscal)], limit=1)
            RegimenFiscal = '%s'%( reg.name )

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
            'RegimenFiscal': RegimenFiscal,
            'EmisorRfc': Emisor.get('Rfc'),
            'EmisorNombre': Emisor.get('Nombre'),
            
            'ReceptorRfc': Receptor.get('Rfc'),
            'ReceptorNombre': Receptor.get('Nombre', ''),
            
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


            valeDespensa = {}
            for percep in Percepciones.get('Lines', []):
                if percep.get('Clave', '') == 'C109':
                    valeDespensa['title'] = 'VALES DE DESPENSA'
                    valeDespensa['importe'] = percep['ImporteExento'] if percep['ImporteExento'] > 0 else percep['ImporteGravado']
                    totalSueldo = Percepciones['TotalSueldos'] - valeDespensa['importe']
                    Percepciones['TotalSueldos'] = totalSueldo
                    break
            if len( Percepciones.get('Lines', []) ) > 0:
                pLines = [i for i in Percepciones['Lines'] if not (i['Clave'] == 'C109')]
                Percepciones['Lines'] = pLines

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
                'Incapacidad': Incapacidad,
                'valeDespensa': valeDespensa
            }
            res.update(resNomina)
        # _logger.info('------report_payslip_params:\n%s', pprint.pformat(res))
        return res

    # -------------------------------------------------------------------------
    # PROCESO TIMBRADO
    # -------------------------------------------------------------------------
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
        self.ensure_one()
        if xml_signed:
            body_msg = _('The sign service has been called with success')
            self.l10n_mx_edi_pac_status = 'signed'
            self.l10n_mx_edi_cfdi = xml_signed
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

    @api.multi
    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return None
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
        totalSepIndem, totalSepIndemGravado, totalSepIndemExento = 0.0, 0.0, 0.0
        totalJubilacion, totalJubilacionGravado, totalJubilacionExento = 0.0, 0.0, 0.0

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
                tipo = percepcion.cfdi_gravado_o_exento or 'gravado'
                # gravado = percepcion.total if tipo == 'gravado' else 0
                # exento = percepcion.total if tipo == 'exento' else 0
                exento = percepcion.total_exento
                gravado = percepcion.total_gravado
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
                    totalSepIndemGravado += gravado
                    totalSepIndemExento += exento
                elif tipo_percepcion in ("039", "044"):
                    totalJubilacion += gravado + exento
                    totalJubilacionGravado += gravado
                    totalJubilacionExento += exento

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
                ultimo_sueldo_mensual = self.get_salary_line_total('SD') * 30
                IngresoNoAcumulable = "%.2f"%(0.0) if totalSepIndemGravado <= 0 else "%.2f"%(totalSepIndemGravado - ultimo_sueldo_mensual)
                IngresoNoAcumulable = "%.2f"%(0.0) if float(IngresoNoAcumulable) <= 0 else IngresoNoAcumulable
                percepciones["SeparacionIndemnizacion"] = {
                    'TotalPagado': "%.2f"%totalSepIndem,
                    'NumAniosServicio': '%s'%round(empleado.cfdi_anhos_servicio),
                    'UltimoSueldoMensOrd': "%.2f"%ultimo_sueldo_mensual,
                    'IngresoAcumulable': "%.2f"%min(totalSepIndemGravado, ultimo_sueldo_mensual),
                    'IngresoNoAcumulable': IngresoNoAcumulable
                }
                percepciones["attrs"]["TotalSeparacionIndemnizacion"] = "%.2f"%totalSepIndem

            if totalJubilacion:
                ultimo_sueldo_mensual = self.get_salary_line_total('SD') * 30
                #-------------------
                # Nodo Jubilación
                #-------------------
                vals = {
                   'TotalUnaExhibición': "%.2f"%totalJubilacion,
                   'IngresoAcumulable': "%.2f"%min(totalJubilacion, ultimo_sueldo_mensual),
                   'IngresoNoAcumulable': "%.2f"%(totalJubilacionGravado - ultimo_sueldo_mensual)
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
                    retenido += abs(deduccion.total)
                else:
                    totalD += abs(deduccion.total)
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
                    'totalDeducciones': abs(totalD) + abs(retenido),
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
                tipo_otro_pago, nombre_otro_pago = self._get_code(otro_pago)
                if otro_pago.total == 0.0 and tipo_otro_pago != '002':
                    continue
                
                nombre_otro_pago = otro_pago.name or ''
                attrs = {
                    'TipoOtroPago': tipo_otro_pago,
                    'Clave': otro_pago.code,
                    'Concepto': nombre_otro_pago.replace(".", "").replace("/", "").replace("(", "").replace(")", ""),
                    'Importe': "%.2f"%abs(otro_pago.total)
                }
                totalOtrosPagos += abs(otro_pago.total)
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

        if TipoRegimen == '02' and (otros_pagos == None or otros_pagos.get('lines', []) == [] ):
        # if TipoRegimen == '02' and otros_pagos == None:
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
        inca_total = self.get_salary_line_total('C110') or 0.0
        nodo_i = self._get_lines_type('i')
        incapacidades = None
        if nodo_i:
            incapacidades = []
            for incapacidad in nodo_i:
                tipo_incapacidad, nombre_incapacidad = self._get_code(incapacidad)
                if incapacidad.total > 0.0:
                    nodo_incapacidad = {
                        "DiasIncapacidad": "%d"%incapacidad.total,
                        "TipoIncapacidad": tipo_incapacidad,
                        "ImporteMonetario": "%.2f"%abs(inca_total),
                    }
                    incapacidades.append(nodo_incapacidad)
        return incapacidades

    # def _get_SalarioBaseCotApor(self):
    #     return self.get_salary_line_total('C510D') or 0.0
    # def _get_SalarioDiarioIntegrado(self):
    #     return self.get_salary_line_total('SD') or 0.0

    def _get_RegistroPatronal(self):
        rp = self.employee_id.cfdi_registropatronal_id and self.employee_id.cfdi_registropatronal_id.code or False
        if rp == False:
            rp = self.company_id.cfdi_registropatronal_id and self.company_id.cfdi_registropatronal_id.code or ''
        return rp

    def _get_NumDiasPagados(self):
        if self.struct_id.l10n_mx_edi_tiponominaespecial in ['ext_fini', 'ext_nom', 'ext_agui']:
            return "1"
        dias = self.get_salary_line_total('C9') or 0.0
        return "%d"%dias

    def _getCompanyName(self):
        companyName = ''
        rp = self.employee_id.cfdi_registropatronal_id and self.employee_id.cfdi_registropatronal_id.address_id or False
        if rp:
            companyName = rp.street_name if rp.street_name else ''
            if rp.street_number:
                companyName += ' %s'%rp.street_number
            if rp.l10n_mx_edi_colony:
                companyName += ' COL. %s'%rp.l10n_mx_edi_colony
            if rp.zip:
                companyName += '  %s'%rp.zip
            if rp.city:
                companyName += '  %s'%rp.city
            if rp.state_id:
                companyName += '  %s'%rp.state_id.name                
        print('--------- companyName ', companyName)
        return companyName.upper()

    @api.multi
    def _l10n_mx_edi_create_cfdi_values(self):
        self.ensure_one()
        empleado = self.employee_id
        company = self.company_id
        fecha_alta = self.contract_id.date_start or empleado.cfdi_date_start or False
        antiguedad = getAntiguedad('%s'%fecha_alta, '%s'%self.date_to)
        RiesgoPuesto = empleado.job_id and empleado.job_id.cfdi_riesgopuesto_id and empleado.job_id.cfdi_riesgopuesto_id.code or False

        if self.cfdi_tipo_nomina == 'E':
            periodicidad_pago = '99'
        else:
            periodicidad_pago = self.contract_id.cfdi_periodicidadpago_id and self.contract_id.cfdi_periodicidadpago_id.code or ""
        banco = False
        num_cuenta = False
        if empleado.bank_account_id:
            banco = empleado.bank_account_id and empleado.bank_account_id.bank_id.bic or ''
            nocuenta = empleado.bank_account_id and empleado.bank_account_id.acc_number or ''
            # num_cuenta = nocuenta[len(nocuenta)-16:]

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
        descuento = TotalDeducciones
        total = subtotal - descuento
        # "%d"%self._get_days("WORK100")[0],
        values = {
            'record': self,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'fiscal_position': self.company_id.partner_id.property_account_position_id,
            'issued': self.journal_id.l10n_mx_address_issued_id,
            'customer': self.employee_id,
            'NumDiasPagados': self._get_NumDiasPagados(),
            "RegistroPatronal": self._get_RegistroPatronal(),
            'antiguedad': antiguedad,
            'fecha_alta': fecha_alta,
            'RiesgoPuesto': RiesgoPuesto,
            'periodicidad_pago': periodicidad_pago,
            'banco': banco,
            'num_cuenta': num_cuenta,
            'TotalPercepciones': "%.2f"%TotalPercepciones,
            'TotalDeducciones': "%.2f"%TotalDeducciones if TotalDeducciones > 0.0 else None,
            'TotalOtrosPagos': "%.2f"%TotalOtrosPagos if TotalOtrosPagos != None else None,
            'EntidadSNCF': EntidadSNCF,
            'Percepciones': Percepciones or None,
            'JubilacionPensionRetiro': JubilacionPensionRetiro,
            'SeparacionIndemnizacion': SeparacionIndemnizacion,
            'Deducciones': Deducciones,
            'OtrosPagos': OtrosPagos,
            'Incapacidades': Incapacidades if Incapacidades and len(Incapacidades) > 0 else None,
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

        total = float(values.get('total', '0.0')) or 0.0
        if total == 0.0:
            return {'no_error': ' No es necesario timbrar este recibo porque el Total es 0.0'}
        importe = float(values.get('importe', '0.0')) or 0.0
        if importe == 0.0:
            return {'no_error': 'No es necesario timbrar este recibo porque no contiene percepciones'}

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
        _logger.info('------------------xmlDatas %s '%xmlDatas )
        """
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
        """
        return {'cfdi': etree.tostring(tree, xml_declaration=True, encoding='UTF-8')}
        # return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    @api.multi
    def l10n_mx_edi_update_pac_status(self):
        '''Synchronize both systems: Odoo & PAC if the invoices need to be signed or cancelled.
        '''
        # elif record.l10n_mx_edi_pac_status in :
        #     record.l10n_mx_edi_retry()
        for record in self:
            if record.state in ['done'] and record.contract_id.is_cfdi and record.l10n_mx_edi_pac_status in ('to_sign', 'retry'):
                record.l10n_mx_edi_retry()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()

    def action_payslip_cfdivalues(self):
        post_msg = []
        body_msg = _('Error: Validacion XML')
        fechaAlta = self.employee_id.cfdi_date_start or self.employee_id.contract_id.date_start or False
        riesgoPuesto = self.employee_id.job_id and self.employee_id.job_id.cfdi_riesgopuesto_id and self.employee_id.job_id.cfdi_riesgopuesto_id.code or False
        # salarioDiarioIntegrado = self.employee_id.cfdi_sueldo_diario and '%.2f'%self.employee_id.cfdi_sueldo_diario or False
        salarioBaseCotApor = self.get_salary_line_total('C510D') or False
        salarioDiarioIntegrado = self.get_salary_line_total('SD') or False
        tipoContrato = self.contract_id.type_id and self.contract_id.type_id.code or ''
        periodicidadPago = self.contract_id.cfdi_periodicidadpago_id and self.contract_id.cfdi_periodicidadpago_id.code or ''
        tipoRegimen = self.contract_id.cfdi_regimencontratacion_id and self.contract_id.cfdi_regimencontratacion_id.code or ''
        registroPatronal = self.company_id.cfdi_registropatronal_id and self.company_id.cfdi_registropatronal_id.code or False
        # total = self.get_salary_line_total('C99')
        # if total <= 0:
        #     post_msg.extend([_('No se puede timbrar Nominas en 0 o Negativos ')])
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
        if not salarioBaseCotApor:
            post_msg.extend([_('El Empleado no tiene "Salario Base de Cotizacion Diario" ')])

        if not registroPatronal:
            post_msg.extend([_('El atributo Nomina.Emisor.RegistroPatronal se debe registrar')])
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
            no_error = cfdi_values.pop('no_error', None)
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                _logger.info('Error %s '%error )
                body = error.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_COMPLEX_TYPE_4: Element '{http://www.sat.gob.mx/nomina12}""", "'")
                body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_MININCLUSIVE_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_MININCLUSIVE_VALID: Element '{http://www.sat.gob.mx/nomina12}""", "")
                body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_PATTERN_VALID: Element '{http://www.sat.gob.mx/cfd/3}""", '')
                body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_CVC_DATATYPE_VALID_1_2_1: Element '{http://www.sat.gob.mx/cfd/3}""", "")
                body = body.replace(""":1:0:ERROR:SCHEMASV:SCHEMAV_ELEMENT_CONTENT: Element: '{http://www.sat.gob.mx/nomina12}""", "")

                # cfdi failed to be generated
                payslip.l10n_mx_edi_pac_status = 'retry'
                payslip.message_post(body=body, subtype='account.mt_invoice_validated')
                return {'error': error}
            if no_error:
                _logger.info('No Timbrado: %s '%no_error )
                payslip.l10n_mx_edi_pac_status = 'none'
                payslip.message_post(body=no_error, subtype='account.mt_invoice_validated')
                return {'no_error': no_error}

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
    def action_payslip_done_cfdi(self):
        error = None
        res = self.action_payslip_cfdivalues()
        if res:
            return False
        # res = super(HrPayslip, self.with_context(without_compute_sheet=True)).action_payslip_done()
        for rec in self:
            # if rec.get_salary_line_total('C99') == 0.0:
            #     rec.message_post(body='Nomina en 0. ')
            #     rec.write({'state': 'done'})
            #     continue
            if rec.contract_id.is_cfdi:
                version = self.l10n_mx_edi_get_pac_version()
                number = rec.number.replace('SLIP','').replace('/','')
                rec.l10n_mx_edi_cfdi_name = ('%s-%s-MX-Payslip-%s.xml' % (rec.journal_id.code, number, version.replace('.', '-'))).replace('/', '')
                result = rec.l10n_mx_edi_retry()
                if result.get('error'):
                    return result
                rec.write({'state': 'done'})
        return res


    #--------------------------------
    # Proceso cancelar timbrado batch
    # Cancelacion Masiva
    #--------------------------------
    @api.multi
    def action_payslip_cancel_cfdis(self):
        def getCodeStatusSat(code=''):
            finkok_codes = {
                '201' : "UUID Cancelado exitosamente",
                '202' : "UUID Previamente cancelado",
                '203' : "UUID No corresponde el RFC del Emisor y de quien solicita la cancelación",
                '205' : "UUID No existe",
                '300' : "Usuario y contraseña inválidos",
                '301' : "XML mal formado",
                '302' : "Sello mal formado o inválido",
                '303' : "Sello no corresponde a emisor",
                '304' : "Certificado Revocado o caduco",
                '305' : "La fecha de emisión no esta dentro de la vigencia del CSD del Emisor",
                '306' : "El certificado no es de tipo CSD",
                '307' : "El CFDI contiene un timbre previo",
                '308' : "Certificado no expedido por el SAT",
                '401' : "Fecha y hora de generación fuera de rango",
                '402' : "RFC del emisor no se encuentra en el régimen de contribuyentes",
                '403' : "La fecha de emisión no es posterior al 01 de enero de 2012",
                '501' : "Autenticación no válida",
                '703' : "Cuenta suspendida",
                '704' : "Error con la contraseña de la llave Privada",
                '705' : "XML estructura inválida",
                '706' : "Socio Inválido",
                '707' : "XML ya contiene un nodo TimbreFiscalDigital",
                '708' : "No se pudo conectar al SAT",
            }
            return finkok_codes.get( code ) or ''

        PayslipModel = self.env['hr.payslip']
        company_id = self.env.user.company_id
        pac_info = self._l10n_mx_edi_finkok_info(company_id, 'cancel')
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']

        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        cer_pem = base64.encodestring(certificate_id.get_pem_cer(
            certificate_id.content)).decode('UTF-8')
        key_pem = base64.encodestring(certificate_id.get_pem_key(
            certificate_id.key, certificate_id.password)).decode('UTF-8')
        uuid_ids = {}
        try:
            client = Client(url, cache=None, timeout=80, plugins=[LogPlugin()])
            invoices_list = client.factory.create("UUIDS")
            for record in self.filtered(lambda p: p.l10n_mx_edi_cfdi_uuid != False):
                uuid_ids[ record.l10n_mx_edi_cfdi_uuid ] = record.id
                invoices_list.uuids.string.append( record.l10n_mx_edi_cfdi_uuid )
            response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem.replace('\n', ''), key_pem)
            _logger.info('-- _nomina_cfdi-reques: Cancel received:\n%s', pprint.pformat(response))
        except Exception as e:
            _logger.info('----------- Error %s '%(e) )
            return False

        msg = ''
        try:
            if hasattr(response, 'CodEstatus'):
                if response.CodEstatus:
                    msg = getCodeStatusSat( response.CodEstatus )
                    self.l10n_mx_edi_log_error( 'CodEstatus: %s '%( response.CodEstatus ) )
                    _logger.info('----------- Error Cancel CodEstatus %s '%( response.CodEstatus ) )
            if not response.Acuse:
                self.l10n_mx_edi_log_error( 'A delay of 2 hours has to be respected before to cancel' )
                _logger.info('A delay of 2 hours has to be respected before to cancel')

            res_folios = ""
            for folios in response.Folios:
                for folio in folios[1]:
                    if folio.EstatusUUID in ('201', '202'):
                        cancelled = True
                        msg = '%s'%( folio.EstatusCancelacion )
                    else:
                        msg = '%s'%( getCodeStatusSat( folio.EstatusUUID ) )
                        cancelled = False
                    uuid = folio.UUID
                    code = folio.EstatusUUID
                    xmlacuse = response.Acuse
                    xmlacuse = xmlacuse[xmlacuse.find("<CancelaCFDResponse"):xmlacuse.find("</s:Body>")]
                    xmlacuse = xmlacuse.replace('<CancelaCFDResponse "', '<CancelaCFDResponse xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance " ')
                    acuse = xmlacuse
                    for slip in PayslipModel.browse(uuid_ids.get(uuid)):
                        slip._l10n_mx_edi_post_cancel_process(cancelled, code, msg, acuse)
                        slip.state = 'cancel'
                        if slip.move_id:
                            slip.move_id.reverse_moves()

        except Exception as e:
            # inv.l10n_mx_edi_log_error(str(e))
            msg = str(e)
            _logger.info('-------------- Error al Cancelar 0 %s '%msg )
        except Exception as e:
            # inv.l10n_mx_edi_log_error(str(e))
            msg = str(e)
            _logger.info('-------------- Error al Cancelar 1 %s '%msg )
        return True

    @api.one
    def action_payslip_cancel_nomina(self):
        if not self.l10n_mx_edi_cfdi_uuid:
            if self.move_id:
                self.move_id.reverse_moves()
            self.state = 'cancel'
            return True
        message = ''
        res = self.cancel()
        if res:
            self.state = 'cancel'
            if self.move_id:
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
        def getCodeStatusSat(code=''):
            finkok_codes = {
                '201' : "UUID Cancelado exitosamente",
                '202' : "UUID Previamente cancelado",
                '203' : "UUID No corresponde el RFC del Emisor y de quien solicita la cancelación",
                '205' : "UUID No existe",
                '300' : "Usuario y contraseña inválidos",
                '301' : "XML mal formado",
                '302' : "Sello mal formado o inválido",
                '303' : "Sello no corresponde a emisor",
                '304' : "Certificado Revocado o caduco",
                '305' : "La fecha de emisión no esta dentro de la vigencia del CSD del Emisor",
                '306' : "El certificado no es de tipo CSD",
                '307' : "El CFDI contiene un timbre previo",
                '308' : "Certificado no expedido por el SAT",
                '401' : "Fecha y hora de generación fuera de rango",
                '402' : "RFC del emisor no se encuentra en el régimen de contribuyentes",
                '403' : "La fecha de emisión no es posterior al 01 de enero de 2012",
                '501' : "Autenticación no válida",
                '703' : "Cuenta suspendida",
                '704' : "Error con la contraseña de la llave Privada",
                '705' : "XML estructura inválida",
                '706' : "Socio Inválido",
                '707' : "XML ya contiene un nodo TimbreFiscalDigital",
                '708' : "No se pudo conectar al SAT",
            }
            return finkok_codes.get( code ) or ''

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
            msg = ''
            try:
                client = Client(url, cache=None, timeout=80, plugins=[LogPlugin()])
                invoices_list = client.factory.create("UUIDS")
                invoices_list.uuids.string = [uuid]
                response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem.replace(
                    '\n', ''), key_pem)
                _logger.info('-- _nomina_cfdi-reques: Cancel received:\n%s', pprint.pformat(response))
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                return False

            try:
                if hasattr(response, 'CodEstatus'):
                    if response.CodEstatus:
                        msg = getCodeStatusSat( response.CodEstatus )
                        inv.l10n_mx_edi_log_error( msg )
                # if not response.Acuse:
                #     inv.l10n_mx_edi_log_error( 'A delay of 2 hours has to be respected before to cancel' )
                for folios in response.Folios:
                    for folio in folios[1]:
                        if folio.EstatusUUID in ('201', '202'):
                            cancelled = True
                            msg = '%s'%( folio.EstatusCancelacion )
                        else:
                            msg = '%s'%( getCodeStatusSat( folio.EstatusUUID ) )
                        code = folio.EstatusUUID
                xmlacuse = response.Acuse
                xmlacuse = xmlacuse[xmlacuse.find("<CancelaCFDResponse"):xmlacuse.find("</s:Body>")]
                xmlacuse = xmlacuse.replace('<CancelaCFDResponse "', '<CancelaCFDResponse xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance " ')
                acuse = xmlacuse

            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                msg = str(e)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                msg = str(e)
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


    #--------------------------------
    # Proceso timbrado batch
    #--------------------------------
    @api.multi
    def _calculation_confirm_sheet(self, ids, use_new_cursor=False):
        message = ''
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))
        message = ""
        try:
            cr.execute('SAVEPOINT model_payslip_confirm_cfdi_save')
            payslip_id = self.env['hr.payslip'].browse(ids)
            payslip_id.action_payslip_done()
            _logger.info('--- Timbrado payslip_id %s '%( payslip_id.id ) )
        except ValueError as e:
            _logger.info('----- Error Timbrado %s %s '%( ids, e ) )
            cr.execute('RELEASE SAVEPOINT model_payslip_confirm_cfdi_save')
            message = str(e)
        except Exception as e:
            _logger.info('----- Error Timbrado %s %s '%( ids, e ) )
            message = str(e)
        if message:
            _logger.info('-------- Error Timbrado %s '%(message) )
            cr.execute('ROLLBACK TO SAVEPOINT model_payslip_confirm_cfdi_save')
        if use_new_cursor:
            cr.commit()
            cr.close()
        return {}    

    #--------------------------------
    # Enviar correo timbrado batch
    #--------------------------------
    @api.multi
    def enviar_nomina(self):
        ctx = self._context.copy()
        template = self.env.ref('l10n_mx_payroll_cfdi.email_template_payroll', False)
        runModel = self.env['hr.payslip.run']
        mailModel = self.env['mail.compose.message']
        for payslip in self:
            if payslip.l10n_mx_edi_cfdi_uuid and payslip.employee_id.address_home_id.email:
                try:
                    ctx.update({
                        'default_model': 'hr.payslip',
                        'mail_post_autofollow': True,
                        'default_composition_mode': 'comment',
                        'default_use_template': bool(template),
                        'default_res_id': payslip.id,
                        'default_template_id': template.id,
                        'force_email': True,
                        'custom_layout': 'mail.mail_notification_light',
                    })
                    vals = mailModel.onchange_template_id(template.id, 'comment', 'hr.payslip', payslip.id)
                    mail_message  = mailModel.with_context(ctx).create(vals.get('value',{}))
                    mailsend = mail_message.action_send_mail()
                    payslip.write({'l10n_mx_edi_sendemail': True})
                except Exception as e:
                    payslip.message_post(body='Error Al enviar Email Nomina %s: %s '%( payslip.number, e ) )
                    _logger.info('------ Error Al enviar Email Nomina %s:  %s '%( payslip.number, e ) )


    def reprocesarNomina(self):
        for payslip in self:
            contract_ids = payslip.contract_id.ids
            for lineDict in payslip._get_payslip_lines(contract_ids, payslip.id):
                total_exento = lineDict.get('total_exento')
                total_gravado = lineDict.get('total_gravado')
                cfdi_codigoagrupador_id = lineDict.get('cfdi_codigoagrupador_id')
                cfdi_tipo_id = lineDict.get('cfdi_tipo_id')
                _logger.info(' -- reprocesarNomina %s - %s '%( cfdi_codigoagrupador_id, cfdi_tipo_id ) )
                for line in payslip.line_ids.filtered(lambda r: r.salary_rule_id.id == lineDict.get('salary_rule_id') and r.code == lineDict.get('code') ):
                    # line.total_exento = total_exento
                    # line.total_gravado = total_gravado
                    line.write({
                        'total_exento': total_exento,
                        'total_gravado': total_gravado,
                        'cfdi_codigoagrupador_id': cfdi_codigoagrupador_id,
                        'cfdi_tipo_id': cfdi_tipo_id
                    })
                    _logger.info(' [%s] - %s Lines %s %s - %s, LE %s - LG %s - LDE %s - LDG %s '%(
                        payslip.id, payslip.employee_id.display_name,
                        line.id, line.code, line.total, line.total_exento, line.total_gravado, total_exento, total_gravado) )
        return True



    def dispersion_bbva_inter_datas_old(self):
        res_banco = []
        indx = 1
        p_ids = self.filtered(lambda r: r.layout_nomina != 'inter' and r.state == 'done' and r.get_salary_line_total('C99') > 0 )
        _logger.info('---------- Layout BBVA Inter %s '%( len(p_ids) ) )
        for slip in p_ids:
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
            # nombre = employee_id.cfdi_complete_name[:40]
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
        print('--- res_banco ', res_banco)
        banco_datas = slip.payslip_run_id._save_txt(res_banco)
        return banco_datas

        # PSC 014180606007975749 000000000156096999 MXP 0000000002905.44 MENDOZA RIVERA PEDRO          40 014 NOMINA 1A MAYO 2021           0020989H
        # PSC014680606009625555000000000156096999MXP0000000003310.09OJEDA VARGAS LEON MAER        40 014 NOMINA 1A MAYO 2021           002099 0H

"""
PSC014180606007975749000000000156096999MXP0000000002905.44MENDOZA RIVERA PEDRO          40014NOMINA 1A MAYO 2021           0020989H

PSC|
014180606007975749|
000000000156096999|
MXP|
0000000002905.44|
MENDOZA RIVERA PEDRO          |
40|
014|
NOMINA 1A MAYO 2021           |
0020989|
H|
"""