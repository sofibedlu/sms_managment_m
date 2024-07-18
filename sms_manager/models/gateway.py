
from odoo import fields, models, api, registry, sql_db
from odoo.exceptions import UserError


# Model for gateway configuration which will be used to send and receive sms(smpp)
# It is used by the sending wizard to send a message
# It is also used by the scheduled actions to make a transreceive bind to the ip
# specified(this method is in receive model.bind_client)
# It is also stored in send and receive models as forign key

class SmsGatewaymodel(models.Model):
    _name = "gateway.sms"
    _description = "Model for the sms gateway "
    _order = "create_date desc"

    # Simple name, url to be used, the username and password, its type, and short code or source address
    name = fields.Char(string="Name")
    url = fields.Char(string="gateway url", required=True)
    username = fields.Char(string="gateway username", required=True)
    pwd = fields.Char(string="gateway password", required=True)
    type = fields.Selection([
        ('http', 'HTTP'),
        ('smpp', 'SMPP'),
    ], 'Gateway Type', default='http')
    default = fields.Boolean("Default Gateway", default=False)
    code = fields.Integer("Short Code")

    # For SMPP ip and port must be provided individually so we need to check
    # We also need only one gateway config to bind to jasmin server so we also need to check that
    # Constraint to check the url as ip:port because of jasmins requirement for SMPP
    # Constraint to check that only one default SMPP exits
    @api.constrains('url', 'type')
    def check_smpp_url(self):
        if self.default == True:
            gateways = self.env["gateway.sms"].search(
                [("type", "=", "smpp"), ("default", "=", "True"), ("id", "!=", self.id)])
            if gateways:
                raise UserError("Only One Default SMPP Gateway can Occur")
        for record in self:
            if (record.type == 'smpp'):
                half_url = self.url.split(':')
                if len(half_url) != 2:
                    raise UserError("Use a ':' separated ip and port for the url if it is smpp")
