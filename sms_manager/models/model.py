import threading
from datetime import datetime
import requests
from odoo import fields, models, api, registry, sql_db, exceptions
from threading import Thread
from odoo.exceptions import UserError
import urllib.request, urllib.error, urllib.parse
import urllib.request, urllib.parse, urllib.error
import json
import base64
import binascii


# Campign based sms marketing, Here we can create campign of 3 different types and then we will
# Parse them to a rest api call and send them to jasmin and jasmin will replay back with a batch id
# We will use that id in our http callback method to match which callback is for which campign
# You can also schedule sms campigns for a later time in which an automated task will check them and
# send them if the time is up
class ListSms(models.Model):
    _name = "list.sms"
    _description = "Model for received sms messages"
    _order = "create_date desc"

    name = fields.Char(string="Subject")
    content = fields.Text(string="Content", required=True)
    # Add a Many2one field for the user
    user_id = fields.Many2one('res.users', string='Sent By', default=lambda self: self.env.user)
    
    type = fields.Selection([
        ('list', 'Contacts'),
        ('number', 'Numbers'),
        ('mail', 'Contact List')], "Campaign Type", default='list')

    # we will need this contact field, the type is list of contacts else its none
    contacts = fields.Many2many("res.partner", string="Recipents")

    # we will need this mail field, the type is mail else its none
    # It is used to locate the mailing list we want to specify
    mail = fields.Many2many("mail.sms", string="Mailing List")

    # we will need these 3 fields, if the type is number  else its none
    # It is used to send sms messages from the starting number to a range we specifiy
    # eg if starting number is 251911000000 and increment is 100
    # it will send to all numbers from 251911000000 to 251911000100
    start = fields.Char(string="Starting Number")
    increment = fields.Integer(string="Range of Nmbers")
    final = fields.Char(String="Last Number")

    # Jasmin Respone, to be used in callback
    batchid = fields.Char(string="Jasmin Id")

    @api.model
    def _get_default_url(self):
        default_gateway = self.env['gateway.sms'].search([('default', '=', True)], limit=1)
        return default_gateway if default_gateway else False
    url = fields.Many2one("gateway.sms", string="Gateway Used", required=True, default=_get_default_url)

    color = fields.Integer(compute='_getColor', store=True)
    status = fields.Selection([
        ('d', 'Draft'),
        ('s', 'Scheduled'),
        ('st', 'Sent'),
        ('dl', 'Delivered'),
        ('c', 'Canceled')
    ], "Status", group_expand='_expand_status')
    now = fields.Boolean("Send Now", default=True)
    send_time = fields.Datetime("Schedule")

    # Total messages in queue of jasmin
    count = fields.Integer("Count", default=0)

    # Total messages acknowledged by call back
    delivered = fields.Integer("Delivered", default=0)

    # link to the NumberLine model
    number_lines = fields.One2many('number.line', 'list_sms_id', string='Numbers')

    # I dont know wat this is
    def _expand_status(self, status, domain, order):
        return [key for key, val in type(self).status.selection]

    # Method used to set color based on status
    @api.depends('status')
    def _getColor(self):
        if self.status == 'd':
            self.color = 5
        elif self.status == 's':
            self.color = 2
        elif self.status == 'st':
            self.color = 10
        elif self.status == 'dl':
            self.color = 15

    # Over ride the create method to send the campign if send now is true
    # Will call 3 different methods depending on the type of campaign, also set the sending time
    @api.model
    def create(self, vals):

        # Create the record first
        rec = super(ListSms, self).create(vals)

        if vals['type'] == 'number' and vals['now']:
            rec.send_time = datetime.now()
            rec.action_send_now(vals)
        elif vals['type'] == 'list' and vals['now']:
            rec.send_time = datetime.now()
            rec.action_send_now(vals)
        elif vals['type'] == 'mail' and vals['now']:
            rec.send_time = datetime.now()
            rec.action_send_now(vals)
        elif not vals['now'] and not vals.get('send_time'):
            rec.status = 'd'
        elif not vals['now'] and vals.get('send_time'):
            rec.status = 's'
            schedule = vals['send_time']
            date = datetime.strptime(schedule, "%Y-%m-%d %H:%M:%S")
            if date < datetime.now():
                raise UserError("Please Schedule For The Future")

        return rec

    # We also over ride the write function to check unwanted edits of campaigns
    # case 1- set send time for draft
    # case 2- remove send time from a scheduled campaign
    # case 3- editing send now boolean

    def write(self, values):
        if 'send_time' in values and self.status == 'd' and values['send_time']:
            schedule = values['send_time']
            date = datetime.strptime(schedule, "%Y-%m-%d %H:%M:%S")
            if date < datetime.now():
                raise UserError("please Schedule For The Future")
            values['status'] = 's'
        elif 'send_time' in values and values['send_time'] == False:
            self.status == 'd'
        elif 'now' in values and self.status == 's':
            raise UserError("Please Press The send Now Button If You want to send now")
        elif 'now' in values and self.status == 'd':
            raise UserError("Please Press The send Now Button If You want to send now")
        # elif self.status == 'st':
        #     raise UserError("You can not alter a sent SMS")
        return super(ListSms, self).write(values)
    

    def action_send_now(self, vals):
        if self.type == 'number':
            self.prepare_number_type(vals)
        elif self.type == 'list':
            self.prepare_list_type(vals)
        elif self.type == 'mail':
            self.prepare_mail_type(vals)

    # prepare the numbers and find the final number of the number type campaign

    #updated the method to use the number_lines field instead of start and increment
    @api.model
    def prepare_number_type(self, vals):
        if not self.number_lines:
            raise UserError("Please add at least one number.")
        response = self.send_batch(vals)
        repo = eval(response.text)
        vals.update({
            'batchid': repo['data']['batchId'],
            'count': repo['data']['messageCount'],
            'status': 'st',
        })
        return vals

    def prepare_mail_type(self, vals):
        numList = []
        # Iterate over each mailing_obj in the Many2many relation
        for mailing_obj in self.mail:
            if mailing_obj.list_type == 'contacts':
                for contact in mailing_obj.contacts:
                    if not contact.mobile:
                        try:
                            num = contact.phone
                            if num:
                                numList.append(num)
                        except:
                            raise UserError(
                                "Please Use an integer in the phone value (omit the + sign) and Start the Campaign Process again")
                    else:
                        num = contact.mobile
                        numList.append(num)
            elif mailing_obj.list_type == 'numbers':
                for number_line in mailing_obj.numbers:
                    numList.append(number_line.number)
        
        # Assuming vals['url'] is provided correctly for a single gateway
        url = self.env['gateway.sms'].browse(vals['url'])
        print(url)
        re = send_same_message_to_many(url.username, url.pwd, url.code, vals['content'], numList, url.url)
        repo = eval(re.text)
        self.batchid = repo['data']['batchId']
        self.count = repo['data']['messageCount']
        self.status = 'st'
        return re

    # fetch all numbers from the databse and pass them to the sending method
    # since this method is called from 2 places check the contacts foreign key
    def prepare_list_type(self, vals):
        numList = []
        print("lets fetch all contacts")
        if len(vals['contacts'][0]) > 1:
            contacts = vals['contacts'][0][2]
        else:
            cont = []
            contacts = vals['contacts']
            for contact in contacts:
                cont.append(contact.id)
            contacts = cont

        for val in contacts:
            recipent = self.env['res.partner'].browse(val)
            if (recipent.mobile == False):
                try:
                    num = recipent.phone
                    numList.append(num)
                except:
                    raise UserError(
                        "Please Use an integer in the phone value(omit the + sign) and Start the Campaign Process again")
            else:
                num = recipent.mobile
                numList.append(num)
        url = self.env['gateway.sms'].browse(vals['url'])
        print(url)
        re = send_same_message_to_many(url.username, url.pwd, url.code, vals['content'], numList, url.url)
        repo = eval(re.text)
        self.batchid = repo['data']['batchId']
        self.count = repo['data']['messageCount']
        self.status = 'st'

        return re

    # this method is called by prepare number type
    # it gets the start and last number and the adds all the numbers in between
    # to a list and passes them to a sending method
    # also fetchs the gateway model from its id in vals
    # returns jasmins response

    #updated the method to use the number_lines field instead of start and increment
    def send_batch(self, vals):
        numlist = [line.number for line in self.number_lines]
        if not numlist:
            print("Warning: numlist is empty. Check if number_lines are properly loaded.")
        url = self.env['gateway.sms'].browse(vals['url'])
        response = send_same_message_to_many(url.username, url.pwd, url.code, self.content, numlist, url.url)
        repo = eval(response.text)
        self.batchid = repo['data']['batchId']
        self.count = repo['data']['messageCount']
        self.status = 'st'
        return response

    # method to convert self(campaign object) to a vals dictionary
    # because create method only accepts dictionary
    def convert_self_to_dict(self, record):
        val = {'type': record.type,
               'start': record.start,
               'mail': record.mail.id,
               'contacts': record.contacts,
               'increment': record.increment,
               'url': record.url.id,
               'content': record.content
               }
        return val

    # Method to be called with an automated scheduled action
    # this will execute every 5 or 10 minutes to see check and execute campaigns
    def scheduled_sender(self):
        campaign_obj = self.env['list.sms'].search([('status', '=', 's')])
        for record in campaign_obj:
            if record.send_time and record.send_time < datetime.now():
                values = self.convert_self_to_dict_for_scheduled(record)
                if record.type == 'number':
                    values = self.prepare_number_type_for_scheduled(values)
                elif values['type'] == 'list':
                    values = self.prepare_list_type_scheduled(values)
                elif values['type'] == 'mail':
                    values = self.prepare_mail_type_scheduled(values)
                record.batchid = values['batchid']
                record.count = values['count']
                record.status = values['status']

    # Method to be called with the send now button on campaign forms of status scheduled and draft
    # This simple calls the previous methods to send the message
    def send_message(self):
        values = {'type': self.type,
                  'start': self.start,
                  'mail': self.mail.id,
                  'contacts': self.contacts,
                  'increment': self.increment,
                  'url': self.url.id,
                  'content': self.content,
                  }
        if values['type'] == 'number':
            values = self.prepare_number_type(values)
        elif values['type'] == 'list':
            values = self.prepare_list_type(values)
        elif values['type'] == 'mail':
            values = self.prepare_mail_type(values)
        self.batchid = values['batchid']
        self.count = values['count']
        self.status = values['status']
        self.send_time = datetime.now()

    # Method to be called with the cancel button on campaign forms of status scheduled
    def cancel_sms(self):
        # Logic to set the status to 'c' for canceled
        self.write({'status': 'c'})

    def reschedule_sms(self):
         # Fetching the schedule_time directly from the record's send_time field
        schedule_time = self.send_time
        if schedule_time:
            # Logic to reschedule the SMS
            # This will also validate the new schedule time
            if schedule_time < fields.Datetime.now():
                raise exceptions.ValidationError("Please schedule for the future.")
            self.write({'send_time': schedule_time, 'status': 's'})
        else:
            raise UserError("Please Enter a Valid Schedule Time")
        
    @api.constrains('send_time')
    def _check_send_time(self):
        for record in self:
            if record.send_time and record.send_time < fields.Datetime.now():
                raise exceptions.ValidationError("Please schedule for the future.")

    def convert_self_to_dict_for_scheduled(self, record):
        val = {'type': record.type,
               'start': record.start,
               'mail': record.mail.ids,
               'contacts': record.contacts,
               'increment': record.increment,
               'url': record.url.id,
               'content': record.content,
               'send_time': record.send_time,
               'number_lines': record.number_lines,
               }
        return val 

    def prepare_number_type_for_scheduled(self, vals):
        if not vals['number_lines']:
            raise UserError("Please add at least one number.")
        response = self.send_batch_for_scheduled(vals)
        repo = eval(response.text)
        vals.update({
            'batchid': repo['data']['batchId'],
            'count': repo['data']['messageCount'],
            'status': 'st',
        })
        return vals
    
    def send_batch_for_scheduled(self, vals):
        numlist = [line.number for line in vals['number_lines']]
        if not numlist:
            print("Warning: numlist is empty. Check if number_lines are properly loaded.")
        url = self.env['gateway.sms'].browse(vals['url'])
        response = send_same_message_to_many(url.username, url.pwd, url.code, vals['content'], numlist, url.url)
        return response
    
    def prepare_list_type_scheduled(self, vals):
        numList = []
        print("lets fetch all contacts")
        if len(vals['contacts'][0]) > 1:
            contacts = vals['contacts'][0][2]
        else:
            cont = []
            contacts = vals['contacts']
            for contact in contacts:
                cont.append(contact.id)
            contacts = cont

        for val in contacts:
            recipent = self.env['res.partner'].browse(val)
            if (recipent.mobile == False):
                try:
                    num = recipent.phone
                    numList.append(num)
                except:
                    raise UserError(
                        "Please Use an integer in the phone value(omit the + sign) and Start the Campaign Process again")
            else:
                num = recipent.mobile
                numList.append(num)
        url = self.env['gateway.sms'].browse(vals['url'])
        response = send_same_message_to_many(url.username, url.pwd, url.code, vals['content'], numList, url.url)
        repo = eval(response.text)
        vals.update({
            'batchid': repo['data']['batchId'],
            'count': repo['data']['messageCount'],
            'status': 'st',
        })
        return vals
    
    def prepare_mail_type_scheduled(self, vals):
        numList = []
        # Since 'mail' is now a Many2many field, we iterate over each mailing_obj
        for mailing_obj in self.env['mail.sms'].browse(vals['mail']):
            if mailing_obj.list_type == 'contacts':
                for contact in mailing_obj.contacts:
                    if not contact.mobile:
                        try:
                            num = contact.phone
                            if num:
                                numList.append(num)
                        except:
                            raise UserError(
                                "Please Use an integer in the phone value (omit the + sign) and Start the Campaign Process again")
                    else:
                        num = contact.mobile
                        numList.append(num)
            elif mailing_obj.list_type == 'numbers':
                # Handling numbers stored in a One2many relationship
                for number_line in mailing_obj.numbers:
                    numList.append(number_line.number)

        url = self.env['gateway.sms'].browse(vals['url'])
        print(url)
        response = send_same_message_to_many(url.username, url.pwd, url.code, vals['content'], numList, url.url)
        repo = eval(response.text)
        vals.update({
            'batchid': repo['data']['batchId'],
            'count': repo['data']['messageCount'],
            'status': 'st',
        })
        return vals


# Parse any data that is to be sent to jasmins rest api
# and encode the username and password with base64 as the jasmin
# documentation
def send_same_message_to_many(uname, pwd, fr, message, numlist, url):
    stringg = str(uname + ':' + pwd)
    stringg = stringg.encode("utf-8")
    auth = base64.b64encode(stringg)
    print(auth)
    auth = "Basic ".encode('utf-8') + auth
    # auth = "Basic cmVraWs6cmVraWs="
    auth = str(auth)
    fr = str(fr)
    print(message)
    # message = message.encode('utf-8')
    # print(message)
    # message = json.dumps(message)
    # print(message)
    # auth = "Basic " + str(auth)
    print(auth)
    message = binascii.hexlify(message.encode('utf-16-be'))
    # message = repr(message)
    message = str(message)
    message = message.replace('b', '', 1)
    message = message.replace("\'", '', 2)
    # message[ = base64.b64encode(message)
    # message = '"' + message + '"'
    # message = message.replace()
    # message = json.dumps(message)  Object of type bytes is not JSON serializable
    print(message)
    print(":Starting")
    u = ""
    if url[0] == "h":
        print("This is HTTP type so cut it")
        print(url)
        temp = url[7:22]
        temp_url = "http://" + temp + ":8080/secure/sendbatch"
        print(temp_url)
        u = temp_url
    else:
        urll = url
        temp_url = "http://" + urll + ":8080/secure/sendbatch"
        print(temp_url)
        u = temp_url
    # url = 'http://127.0.0.1:8080/secure/sendbatch'
    # header = {'Authorization': 'Basic aGVsbG86aGVsbG8='}
    header = {'Authorization': auth}
    print(header)
    # prepare the payload and then add the neccessary numbers in the list
    payload = {

        "batch_config": {
            "callback_url": "http://127.0.0.1:8069/restcallback",
            "errback_url": "http://127.0.0.1:8069/restcallback"
        },
        "messages": [
            {
                "to": [

                ],
                "from": fr,
                "coding": '9',
            }
        ]
    }
    for num in numlist:
        if num is False:
            continue
        num = num.replace(" ", "")
        num = num.strip()
        if num[0] == "+":
            num = num[1:]
        payload.get("messages")[0].get("to").append(num)
    payload.get("messages")[0].__setitem__("hex_content", message)
    payload = str(payload)  # jason can't handle dictionary
    payload = payload.replace("\'", "\"")
    # don't try this payload = json.dumps(payload)
    print(payload)
    # payload = payload.replace("[", "")
    # payload = payload.replace("]", "")
    print("payload is " + str(payload))

    try:
        """print("you are here")
        print(str(u))
        urllib.request.urlopen(str(u) % urllib.parse.urlencode(payload)).read()"""
        # payload = json.dumps(payload)
        response = requests.post(u, headers=header, data=payload)
        print(response)
        print(response.status_code)

        # st_code = response.status_code
        # if st_code != 200:
        #     raise UserError(
        #         str(response.status_code) + " code :" + "An Error Ocuured please check your configuration settings")
        return response
    except Exception as e:
        print(e)
        print(e.__str__())
        raise UserError("Error Occured please check the server")
# To do
# 1. check if message content contians unique characters or other languege before passing to payload

