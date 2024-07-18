# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Jasmin Sms Manager',
    'version': '13.1.1',
    'summary': 'Tool used to send and receive sms messages from jasmin server',
    'sequence': 15,
    'description': "Helps send bulk sms to jasmin's sms gateway. And receive sms in a stateful SMPP protocool",
    'category': 'Tools',
    'depends': [
        'web_notify', 'base'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/received.xml',
        'views/gateway.xml',
        'views/filters.xml',
        'views/sentsms.xml',
        'views/wizards.xml',
        'data/actions.xml',
        'reports/reportsfilter.xml',
        'reports/reportsreceived.xml',
        "views/listsms.xml",
        "views/mail.xml",
        "reports/SMScampaignreport.xml",
        "reports/SMScampaignreportgenerator.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
