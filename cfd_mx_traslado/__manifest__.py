# -*- coding: utf-8 -*-
{
    'name': "CFDI Traslado",
    'summary': u"""
El CFDI de Traslado es un documento fiscal que sirve 
para amparar la propiedad de las mercancías que requieren 
transportar por la vía terrestre dentro del territorio nacional o extranjero.""",
    'description': u"""
El CFDI de Traslado es un documento fiscal que sirve 
para amparar la propiedad de las mercancías que requieren 
transportar por la vía terrestre dentro del territorio nacional o extranjero.
    """,
    'author': "OpenBias",
    'website': "https://bias.com.mx",
    'category': 'Uncategorized',
    'version': '1.5',
    'depends': ['base_setup', 'l10n_mx_edi', 'l10n_mx_edi_extended', 'account', 'stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/cfdi_traslados_data.xml',
        'data/csv/cfdi.cartaporte.estaciones.csv',
        'data/csv/cfdi.cartaporte.unidadpeso.csv',
        'data/csv/cfdi.cartaporte.clavestcc.csv',
        'data/csv/cfdi.cartaporte.materialpeligroso.csv',
        'data/csv/cfdi.cartaporte.embalaje.csv',
        'data/csv/cfdi.cartaporte.tipopermiso.csv',
        'data/csv/cfdi.cartaporte.configvehicular.csv',
        'data/csv/cfdi.cartaporte.subtiporemolque.csv',

        'views/cfdi_cartaporte_transporte_views.xml',
        'views/cfdi_cartaporte_views.xml',
        'views/cfdi_traslados_views.xml',
        'views/report_cfdi_cartaporte_views.xml',
        'views/cfdi_cartaporte_menu.xml'
    ]
}