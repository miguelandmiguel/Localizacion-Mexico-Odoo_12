# -*- coding: utf-8 -*-
{
    'name': "MX Addenda",
    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",
    'description': """
        Long description of module's purpose
    """,
    'author': "OpenBias",
    'website': "https://www.bias.com.mx",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'account', 'l10n_mx_edi'],
    'data': [
        'security/ir.model.access.csv',
        'data/addenda/coppel.xml',
        'views/views.xml',
        # 'views/templates.xml',
    ]
}


# python3 ./odoo-bin -c ../hr_odoo.conf -d odoo12_repNom --db-filter=odoo12_repNom  -u l10n_mx_addenda --max-cron-threads=0 --stop-after-init --no-xmlrpc

# UPDATE ir_module_module set state = 'to upgrade' where name = 'my_module';