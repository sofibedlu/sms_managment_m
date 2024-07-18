import requests
from odoo import fields, models, api, registry, sql_db
from threading import Thread
from odoo.exceptions import UserError

import smpplib.gsm
import smpplib.client
import smpplib.consts
import smpplib
import logging
import sys


# Model for received messages from jasmin gateway
class ReceivedSms(models.Model):
    _name = "r.sms"
    _description = "Model for received sms messages"
    _order = "create_date desc"

    content = fields.Char(string="Contents", required=True)
    fr = fields.Char(string="From")
    partner_id = fields.Many2one("res.partner", string="Contact")
    other_sms_ids = fields.Many2many("s.sms", string="Conversations")
    # permissions = fields.Many2one("res.partner", string="Permissions")
    owners = fields.Many2many("res.users", string="Owner")

    # Method to execute upon receiving the SMS
    def getPdu(self, pdu):
        print(self.env)
        print(pdu.sequence)
        with api.Environment.manage():
            # As this function is in a new thread, I need to open a new cursor, because the old one may be closed
            new_cr = self.pool.cursor()
            self = self.with_env(self.env(cr=new_cr))
            source_address = pdu.source_addr
            if not source_address:
                source_address = "111"
            newrsms = self.env['r.sms']
            # check if the sender is in our database of contacts
            findcontact = self.env['res.partner'].search([('mobile', '=', source_address)]).id
            user = self.env['res.partner'].browse(findcontact)
            if (findcontact == False):
                print("no user found")
                user = self.env.user
                print(user)
                vals = {
                    'content': pdu.short_message.decode('utf-8'),
                    'fr': source_address,
                    'partner_id': None,
                    'other_sms_ids': None,
                    'owners': user}
                newrsms.create(vals)
                self.env.cr.commit()
                user.notify_info(message='Message Received,Unknown User so it has been assigned to you')
                return
            # check if a messages has been sent to this address before, if so fetch all ids and put them as conversation
            findsent = self.env['s.sms'].search([('to', '=', source_address)])
            print(findsent)
            savesent = []
            saveowners = []
            for sent in findsent:
                savesent.append(sent.id)
                saveowners.append(sent.create_uid.id)
                sent.create_uid.notify_info(message='Message Received')
            print(savesent)
            print(saveowners)
            saveowners = set(saveowners)
            print(saveowners)
            saveowners = tuple(saveowners)
            print(saveowners)
            vals = {
                'content': pdu.short_message.decode('utf-8'),
                'fr': source_address,
                'partner_id': user.id,
                'other_sms_ids': savesent,
                'owners': saveowners}
            newrsms.create(vals)
            self.env.cr.commit()

    # This is the method to be called with an automated action, it will try to fetch an SMPP
    # configured gateway that is set as default and it will use the data from that gateway
    # to contect to Jasmins SMPP listener
    # So then after contecting and binding it will listen on a new thread for incoming messages
    # and when ever they arrive self.getPdu(pdu) method is called which will save it to database
    def bind_client(self):
        users = self.env['res.users'].search([])
        print(users)
        for user in users:
            user.notify_info(message="Listening to Jasmin Server")
        gateways = self.env["gateway.sms"].search([("type", "=", "smpp"), ("default", "=", True)])
        if not gateways:
            print("Gateway not found to listen to")
            # self.env.user.notify_info(message="Please Insert Jasmin gateway creditionals to receive messages")
            for user in users:
                user.notify_info(message="Please Insert Jasmin gateway creditionals to receive messages")
            return True
        username = gateways[0].username
        password = gateways[0].pwd
        half_url = gateways[0].url.split(':')
        print(half_url)
        logging.basicConfig(level='DEBUG')
        client = smpplib.client.Client(half_url[0], half_url[1])
        client.set_message_received_handler(
            lambda pdu: self.getPdu(pdu))
        client.set_message_sent_handler(
            lambda pdu: sys.stdout.write('sent {}\n'.format(pdu.receipted_message_id)))
        client.connect()
        client.bind_transceiver(system_id=username, password=password)
        print("binding to client")
        t = Thread(target=client.listen, args=self)
        t.daemon = True
        t.start()
        #threading.Timer(5, t.join())

        while not t.is_alive():
            self.env.user.notify_info(message="Stopped Listening to Jasmin Server")
            pass
        return True
