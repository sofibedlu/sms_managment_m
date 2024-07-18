# Model for filtering received sms
from odoo import fields, models, api, registry, sql_db


# A model created for store filters(contents)  which will be matched
# with receiving messages content, if they do match they will be added tothe many to many field
# it is used to show messages that match a certain filter

class SmsContentFilter(models.Model):
    _name = "filter.sms"
    _description = "To filter out received sms messages based on content"
    _order = "create_date desc"

    # # parameters, the filter to match, the matching messages and their count
    filter = fields.Char(string="Filter", required=True)
    sms_ids = fields.Many2many("r.sms", string="Matching messages", domain="[('content','=',filter)]", store=True)
    count = fields.Integer(compute='_count', store=True)

    # auto_add = fields.Boolean("Auto Add", default = True)

    # compute the count(total) number of matching messages
    @api.depends('sms_ids')
    def _count(self):
        i = 0
        for sms in self.sms_ids:
            i = i + 1
        self.count = i
