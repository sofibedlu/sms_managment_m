import urllib

import requests
from odoo import fields, models, api
from odoo.exceptions import UserError

import smpplib
import smpplib.gsm
import smpplib.client
import smpplib.consts
import logging

import sys

_logger = logging.getLogger(__name__)

#This wizard shows all messages sent and received from and to the same number
class SmsWizard(models.TransientModel):
    _name = "all.sms"
    _description = "A Wizard for seeing all messages"

    def _defaultsent(self):
        active = self._context.get('active_id')
        env = self.env["r.sms"].browse(active)
        return env.other_sms_ids

    def _defaultreceived(self):
        active = self._context.get('active_id')
        active_sms = self.env['r.sms'].search([('id', '=', active)])
        # env=self.env["res.partner"].search([('mobile', '=', active.contact.mobile)])
        received = self.env["r.sms"].search([('partner_id', '=', active_sms.partner_id.id)])
        return received

    sms_sent = fields.Many2many("s.sms", string="Sent Messages", default=_defaultsent)
    received = fields.Many2many("r.sms", string="Received Messages", default=_defaultreceived)

# This wizard is used to show the vbalance and message count of the selected gateway configuration
# It makes a url request to jasmin server wit the given uname and pw
class SmsWizard(models.TransientModel):
    _name = "balance.sms"
    _description = "Wiz for checking balance sms"

    def _getBalance(self):
        active = self._context.get('active_id')
        env = self.env["gateway.sms"].browse(active)

        url = "http://127.0.0.1:1401/balance"
        pwd = env.pwd
        print(pwd)
        username = env.username
        print(username)
        param = {
            'username': username,
            'password': pwd
        }
        url = url
        print(url)
        try:
            response = requests.get(url, param)
            print(response)
            data = response.json()
            print(data)
            return data['balance']
        except:
            UserError("Something when wrong,check connection or gateway configuration")

    def _getSms_count(self):
        active = self._context.get('active_id')
        env = self.env["gateway.sms"].browse(active)
        url = "http://127.0.0.1:1401/balance"
        pwd = env.pwd
        print(pwd)
        username = env.username
        print(username)
        param = {
            'username': username,
            'password': pwd
        }
        url = url
        print(url)
        try:
            response = requests.get(url, param)
            print(response)
            data = response.json()
            print(data)
            return data['sms_count']
        except:
            UserError("Something when wrong,check connection or gateway configuration")

    sms_count = fields.Char(string="Count Sms", default=_getSms_count)
    balance = fields.Char(string="balance", default=_getBalance)

# A wizard used to send single message to a certain number
# It has 2 types with HTTP and SMPP, each have their own method
class SMS(models.TransientModel):
    _name = "send.sms"
    _description = "A Wizard for sending sms messages"

    def _default_to(self):
        active = self._context.get('active_id')
        print(active)
        user = self.env["res.partner"].browse(active)
        number = user.mobile
        if (number == False):
            number = user.phone
        return number

    to = fields.Char(string="To", default=_default_to, required=True)
    message = fields.Text(string="Message", required=True)
    gateway = fields.Many2one("gateway.sms", string="Gateway", required=True)

    def send_message(self):
        url = self.gateway
        msg = self.message
        dest = self.to
        un = self.gateway.username
        pwd = self.gateway.pwd
        fr = self.gateway.code
        gateway_type = self.gateway.type
        if gateway_type == 'http':
            self.send_with_http(url, un, pwd, msg, dest, fr)
        else:

            self.send_with_smpp(url, un, pwd, msg, dest, fr)
        return {'type': 'ir.actions.act_window_close'}

    def send_with_http(self, urls, username, password, mssg, des, fr):
        try:
            print(urls, username, password, mssg, des)
            param = {
                "username": username,
                "password": password,
                "content": mssg,
                "to": des,
                "from": fr
            }
            # url=sms.name+"&"+"content="+sms.msg+"&"+"to="+sms.mobile
            url = urls.url + "?" + urllib.parse.urlencode(param)
            print(url)
            r = urllib.request.urlopen(url)
            print(r)
            vals = {
                'msg': mssg,
                'to': des,
                'url': urls.id,
            }
            self.save_sms(vals)
        except:
            raise UserError('Failure Occured,Please check gateway configurations or if your server is running')
        pass

    def send_with_smpp(self, url, username, password, msg, des, fr):
        print(url, username, password, msg, des)
        self.call_to_smpp(url, username, password, msg, des, fr)
        pass

    def save_sms(self, vals):
        print("Saving")
        newsms = self.env["s.sms"]
        newsms.create(vals)
        self.env.cr.commit()
        self.env.user.notify_info(message='Message Sent and Saved')
        return

    def call_to_smpp(self, gateway, username, password, msg, des, fr):
        half_url = gateway.url.split(':')
        print(half_url[0] + "  " + half_url[1])
        if type(fr) == int:
            fr = str(fr)
        if type(des) == int:
            des = str(des)
        try:
            logging.basicConfig(level='DEBUG')

            parts, encoding_flag, msg_type_flag = smpplib.gsm.make_parts(msg)
            print(parts)

            client = smpplib.client.Client(half_url[0], half_url[1])

            client.set_message_sent_handler(
                lambda pdu: print("sent"))

            def setdlr():
                print("setting")

            client.set_message_received_handler(
                lambda pdu: setdlr())

            client.connect()
            client.bind_transmitter(system_id=username, password=password)

            for part in parts:
                print(part)
                pdu = client.send_message(
                    source_addr_ton=smpplib.consts.SMPP_TON_INTL,
                    # source_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                    # Make sure it is a byte string, not unicode:
                    source_addr=fr,

                    dest_addr_ton=smpplib.consts.SMPP_TON_INTL,
                    # dest_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                    # Make sure thease two params are byte strings, not unicode:
                    destination_addr=des,
                    short_message=part,
                    data_coding=encoding_flag,
                    esm_class=msg_type_flag,
                    registered_delivery=False,
                )
                print(pdu.sequence)
                vals = {
                    'msg': msg,
                    'to': des,
                    'url': gateway.id,
                }
                self.save_sms(vals)
        except:
            print("Oops!", sys.exc_info()[0], "occurred.")
            raise UserError("Failure Occured,Please check gateway configurations or if your server is running")

# send mass messages to child objects of a company
# just call the above 2 types of methods in a for loop
class SMS(models.TransientModel):
    _name = "mass.sms"
    _description = "A Wizard for sending mass sms messages"

    message = fields.Text(string="Message", required=True)
    gateway = fields.Many2one("gateway.sms", string="Gateway", required=True)

    def send_mass_sms(self):
        message = self.message
        gateway = self.gateway
        active_ids = self._context.get('active_ids')
        print(active_ids)
        partner_obj = self.env['res.partner']
        send = self.env['send.sms']
        partner = partner_obj.browse(active_ids[0])
        if not partner.child_ids:
            raise UserError("please select Compnay with one or more employee")
            # return {'type': 'ir.actions.act_window_close'}
        for child in partner.child_ids:
            if (child.mobile == False):
                try:
                    to = int(child.phone)
                except:
                    raise UserError(
                        "Please Use an integer in the phone value(omit the + sign) and Start the Campaign Process again")
            else:
                to = int(child.mobile)
            # to = child.mobile
            if gateway.type == 'http':
                send.send_with_http(gateway, gateway.username, gateway.pwd, message, to, gateway.code)
            else:
                half_url = gateway.url.split(':')
                send.send_with_smpp(gateway, gateway.username, gateway.pwd, message, to, gateway.code)

        return {'type': 'ir.actions.act_window_close'}
