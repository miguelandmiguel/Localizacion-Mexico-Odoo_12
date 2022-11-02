# -*- coding: utf-8 -*-

from odoo import _, api, fields, models, tools, registry, SUPERUSER_ID

class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    grupo_afinidad = fields.Char(
        string='Grupo Afinidad', copy=False, readonly=False,
        help='GRUPO DE AFINIDAD ASIGNADO POR BANCO DEL BAJIO A LA EMPRESA.')

