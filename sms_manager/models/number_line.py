from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re

class NumberLine(models.Model):
    _name = 'number.line'
    _description = 'Number Line'

    list_sms_id = fields.Many2one('list.sms', string='List SMS')
    mail_sms_id = fields.Many2one('mail.sms', string='Mail SMS')
    number = fields.Char(string='Number', required=True)

    @api.constrains('number')
    def _check_number_format(self):
        pattern = re.compile(r'^0\d{9}$')
        for record in self:
            if not pattern.match(record.number):
                raise ValidationError("Number must be a 10-digit number starting with 0.")