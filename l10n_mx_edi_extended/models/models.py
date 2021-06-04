# coding: utf-8

from odoo import api, fields, models, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_noidentificacion = fields.Selection(
        selection=[
            ('defaultcode', "Referencia Interna"),
            ('barcode', "Codigo de Barras")
        ],
        string="CFDI No Identificacion", default='defaultcode')


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    def getNoIdentificacion(self):
        noIdentificacion = self.product_id.default_code if self.partner_id.l10n_mx_edi_noidentificacion == 'defaultcode' else self.product_id.barcode
        return self.invoice_id._get_string_cfdi( noIdentificacion or '' )