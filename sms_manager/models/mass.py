from odoo import fields, models, api, registry, sql_db


# Simple mailing list to be used over and over again to create a campign that uses a defined
# list of contacts
class MailList(models.Model):
    _name = "mail.sms"
    _description = "Model for a Group Of Recioents"
    _order = "create_date desc"

    # Simlpe name, its descriptions and a list of contacts that have mobile or
    # phone number set
    name = fields.Char("Name")
    descri = fields.Char("Info")
    contacts = fields.Many2many("res.partner", string="Recipents")
    total = fields.Integer("Total", compute="_getTotal", store=True)

    # Add a selection field to choose between contacts and numbers
    list_type = fields.Selection([
        ('contacts', 'Contacts'),
        ('numbers', 'Numbers')
    ], default='contacts', string="List Type")
    #Add a field to store the numbers
    numbers = fields.One2many("number.line", "mail_sms_id", string="Numbers")

    @api.depends('contacts', 'numbers')
    def _getTotal(self):
        if self.list_type == 'contacts':
            self.total = len(self.contacts)
        elif self.list_type == 'numbers':
            self.total = len(self.numbers)
