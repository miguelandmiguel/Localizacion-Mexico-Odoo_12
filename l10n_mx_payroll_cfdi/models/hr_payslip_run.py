# -*- coding: utf-8 -*-
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, tools
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr
from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

_logger = logging.getLogger(__name__)

CATALOGO_TIPONOMINA = [('O','Ordinaria'), ('E','Extraordinaria')]

def create_list_html(array):
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'

class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    @api.one
    @api.depends('slip_ids', 'slip_ids.state', 'slip_ids.l10n_mx_edi_cfdi_uuid')
    def _compute_state(self):
        eval_state = True if self.eval_state else False
        state = 'draft'
        if len(self.slip_ids) == 0:
            state = 'draft'
        elif any(slip.state == 'draft' for slip in self.slip_ids):  # TDE FIXME: should be all ?
            state = 'draft'
        elif all(slip.state in ['cancel', 'done'] for slip in self.slip_ids):
            state = 'close'
        else:
            state = 'draft'
        self.state = state
        return True

    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=False,
        index=True, store=True, copy=False)  # related is required

    eval_state = fields.Boolean('Eval State', compute='_compute_state')
    cfdi_es_sncf = fields.Boolean(string='Entidad SNCF', readonly=True, compute='_compute_cfdi_sncf', oldname="es_sncf")
    cfdi_source_sncf = fields.Selection([
            ('IP', 'Ingresos propios'),
            ('IF', 'Ingreso federales'),
            ('IM', 'Ingresos mixtos')],
        string="Recurso Entidad SNCF", oldname="source_sncf")
    cfdi_amount_sncf = fields.Float(string="Monto Recurso SNCF", oldname="amount_sncf")

    cfdi_date_payment = fields.Date(string="Fecha pago", required=True, default=lambda self: fields.Date.to_string(date.today().replace(day=1)), oldname="fecha_pago")
    cfdi_tipo_nomina_especial = fields.Selection([
            ('ord', 'Nomina Ordinaria'),
            ('ext_nom', 'Nomina Extraordinaria'),
            ('ext_agui', 'Extraordinaria Aguinaldo')],
        string="Tipo Nomina Especial", default="ord", oldname="tipo_nomina_especial")
    cfdi_tipo_nomina = fields.Selection(selection=CATALOGO_TIPONOMINA, string=u"Tipo Nómina", default='O', compute='_compute_cfdi_sncf', oldname="tipo_nomina")
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
        readonly=True, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},
        help='Defines the rules that have to be applied to this payslip, accordingly '
             'to the contract chosen. If you let empty the field contract, this field isn\'t '
             'mandatory anymore and thus the rules applied will be all the rules set on the '
             'structure of all contracts of the employee valid for the chosen period')

    @api.one
    @api.depends('slip_ids', 'cfdi_source_sncf', 'cfdi_amount_sncf', 'cfdi_tipo_nomina_especial')
    def _compute_cfdi_sncf(self):
        cfdi_tipo_nomina = 'O' if self.cfdi_tipo_nomina_especial == 'ord' else 'E'
        self.cfdi_es_sncf = True if self.cfdi_source_sncf else False
        self.cfdi_tipo_nomina = cfdi_tipo_nomina
        self.sudo().slip_ids.write({
            "cfdi_source_sncf": self.cfdi_source_sncf,
            "cfdi_amount_sncf": self.cfdi_amount_sncf,
            "cfdi_tipo_nomina": cfdi_tipo_nomina,
            "cfdi_tipo_nomina_especial": self.cfdi_tipo_nomina_especial
        })
        return True

    @api.multi
    def confirm_sheet_run(self):
        self.ensure_one()
        cr = self._cr
        payslip_obj = self.env['hr.payslip']
        for payslip_id in self.slip_ids.ids:
            try:
                cr.execute('SAVEPOINT model_payslip_confirm_cfdi_save')
                payslip = payslip_obj.browse(payslip_id)
                if payslip.state in ['draft','verify']:
                    _logger.info('------------ confirm_sheet_run %s - %s '%(payslip.id, payslip.number) )
                    try:
                        payslip.action_payslip_done()
                    except Exception as e:
                        payslip.message_post(body='Error al procesar: %s '%(e)  )
                cr.execute('RELEASE SAVEPOINT model_payslip_confirm_cfdi_save')
            except Exception as e:
                _logger.exception('----- Error: %s '%(e) )
                cr.execute('ROLLBACK TO SAVEPOINT model_payslip_confirm_cfdi_save')
                pass
        return

    @api.multi
    def enviar_nomina(self):
        self.ensure_one()
        ctx = self._context.copy()
        template = self.env.ref('l10n_mx_payroll_cfdi.email_template_payroll', False)
        for payslip in self.slip_ids: 
            ctx.update({
                'default_model': 'hr.payslip',
                'default_res_id': payslip.id,
                'default_use_template': bool(template),
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
            })
            vals = self.env['mail.compose.message'].onchange_template_id(template.id, 'comment', 'hr.payslip', payslip.id)
            mail_message  = self.env['mail.compose.message'].with_context(ctx).create(vals.get('value',{}))
            mail_message.action_send_mail()
        return True