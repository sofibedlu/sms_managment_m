from openerp import http
from werkzeug.wrappers import Response


class Home(http.Controller):

    # This class contains http listeners for incoming messages and for rest call back messages
    # For the future also, it will listen for dlr messages for jasmin

    # ---- This route mosms -----
    # http listner to accept messages from jasmin mo router and
    # will check both for related messages and if contacts are available
    # check if the contents of the message match a given filter
    # save the received messages to r.sms database table
    @http.route('/mosms', type='http', auth="none", methods=['GET'])
    def index(self, **kwargs):
        print(kwargs)
        Response.status = '200'
        received_oboj = http.request.env['r.sms'].sudo()
        try:
            source_address = kwargs['from']
        except:
            return "Empty Param"
        if not source_address:
            source_address = "111"
        findcontact = http.request.env['res.partner'].sudo().search([('mobile', '=', source_address)]).id
        user = http.request.env['res.partner'].sudo().browse(findcontact)
        if (findcontact == False):
            print("no user found")
            user = http.request.env.user
            print(user)
            vals = {
                'content': kwargs['content'],
                'fr': source_address,
                'partner_id': None,
                'other_sms_ids': None,
                'owners': user}
            rece = received_oboj.create(vals)
            self.check_filter(rece)
            http.request.env.cr.commit()
            return "ACK/Jasmin"
        # check if a messages has been sent to this address before, if so fetch all ids and put them as conversation
        findsent = http.request.env['s.sms'].sudo().search([('to', '=', source_address)])
        print(findsent)
        savesent = []
        saveowners = []
        for sent in findsent:
            savesent.append(sent.id)
            saveowners.append(sent.create_uid.id)
            # sent.create_uid.notify_info(message='Message Received')
        saveowners = set(saveowners)
        saveowners = tuple(saveowners)
        vals = {
            'content': kwargs['content'],
            'fr': source_address,
            'partner_id': user.id,
            'other_sms_ids': savesent,
            'owners': saveowners}
        rece = received_oboj.create(vals)
        self.check_filter(rece)
        http.request.env.cr.commit()
        return "ACK/Jasmin"

    # ---- This method check_filter -----
    # Method to check is a given r.sms object(received message) matches a filter
    def check_filter(self, received_obj):
        filter = http.request.env['filter.sms'].sudo().search(
            [('filter', '=', received_obj.content)
             # ,('auto_add', '=', True)
             ])
        filter.write({'sms_ids': [(4, received_obj.id)]})
        print(filter)

    # ---- This route dlr -----
    # for the future version, to check delivery of messages
    @http.route('/dlr', type='http', auth="none", methods=['GET'])
    def index2(self, **kwargs):
        print(kwargs)
        Response.status_code = '200'
        return "ACK/Jasmin"

    # ---- This route restcallback -----
    # Rest call back route,used to receive success and error call backs
    # for messages sent with the rest api
    # finds a campign with its batchId then ceck the success and add a count to delivered
    @http.route('/restcallback', type='http', auth="none", methods=['GET'])
    def call_back(self, **kwargs):
        print(kwargs)
        campign_obj = http.request.env['list.sms'].sudo().search([('batchid', '=', kwargs['batchId'])])
        check = kwargs['statusText'][0:7]
        if check == 'Success':
            campign_obj.delivered += 1

        if campign_obj.count == campign_obj.delivered:
            campign_obj.status = 'dl'
        return "hello world rest"

    # ---- This route mosmsvote -----
    # A route to receive messages as votes, it will not check for anything just save them
    # Also checks if they match a filter
    @http.route('/mosmsvote', type='http', auth="none", methods=['GET'])
    def vote(self, **kwargs):
        Response.status = '200'
        received_oboj = http.request.env['r.sms'].sudo()
        try:
            source_address = kwargs['from']
        except:
            return "Empty Param"
        vals = {
            'content': kwargs['content'],
            'fr': source_address,
            'partner_id': None,
            'other_sms_ids': None,
            'owners': None}
        rece = received_oboj.create(vals)
        if rece is False:
            return "No/Jssmin"
        self.check_filter(rece)
        http.request.env.cr.commit()
        return "ACK/Jasmin"
