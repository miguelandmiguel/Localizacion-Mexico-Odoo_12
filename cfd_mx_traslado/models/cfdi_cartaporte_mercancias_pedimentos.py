# -*- coding: utf-8 -*-

from odoo import api, fields, models, SUPERUSER_ID, _

# Mercancia => Pedimentos
class CfdiMercanciaPedimentos(models.Model):
    _name = 'cfdi.cartaporte.mercancias.pedimentos'
    _description = 'Mercancias Pedimentos'

    name = fields.Char(string='Pedimento', 
        help = u"Atributo requerido para expresar el número de "
            u"pedimento  de  importación  que  se  encuentra  asociado "
            u"con el traslado de los bienes y/o mercancías de "
            u"procedencia extranjera para acreditar la legal estancia "
            u"y tenencia durante su traslado en territorio nacional, el "
            u"ual  se  expresa  en  el  siguiente  formato:  últimos  2 "
            u"dígitos del año de validación seguidos por dos espacios, "
            u"2 dígitos de la aduana de despacho seguidos por dos "
            u"spacios, 4 dígitos del número de la patente seguidos por "
            u"dos espacios, 1 dígito que corresponde al último dígito "
            u"del  año  en  curso,  salvo  que  se  trate  de  un  pedimento "
            u"consolidado iniciado en el año inmediato anterior o del "
            u"pedimento  original  de  una  rectificación,  seguido  de  6 "
            u"dígitos de la numeración progresiva por aduana.")
    sequence = fields.Integer(string='sequence')
    mercancia_id = fields.Many2one('cfdi.cartaporte.mercancias', string='CFDI Mercancias', ondelete='cascade', index=True)
