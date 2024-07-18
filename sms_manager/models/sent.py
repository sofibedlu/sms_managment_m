from odoo import fields, models, api, registry, sql_db


# model for sent sms
class SmsSentmodel(models.Model):
    _name = "s.sms"
    _description = "Model for sent sms "
    _order = "create_date desc"

    url = fields.Many2one("gateway.sms", string="Gateway Used", required=True)
    msg = fields.Text(string="message", required=True)
    status = fields.Selection([
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
    ], 'Message Status', default='sent')
    to = fields.Char(string="To", required=True)