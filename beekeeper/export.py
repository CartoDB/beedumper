import requests
from collections import namedtuple
from pathlib import Path
import json

class Exporter(object):
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({ 'Accept' : 'application/json', 'Cache-Control' : 'no-cache', 'Content-Type': 'application/json'})
        self.session.params.update({ 'auth_token' : config['token'], 'per_page' : config['per_page']})
        self.url = config['url']
    
    def get_config(self):
        return self.config

    def get_data(self, endpoint, params = {}):
        r = self.session.get(url=self.url + endpoint, params=params)
        if r.status_code == 200:
            return r.json()
        else:
            import ipdb; ipdb.set_trace()
            raise Exception(r.text)
    
    def get_users(self):
        data = self.get_data('/users', params={'with_invited' : True})
        return data['users']

    def get_labels(self):
        data = self.get_data('/labels')
        return data['labels']

    def get_teams(self):
        data = self.get_data('/teams')
        return data['teams']

    def get_snippets(self):
        data = self.get_data('/snippets')
        return data['snippets']
    
    def get_emails(self):
        data = self.get_data('/emails')
        return data['forwarding_addresses']
    
    def get_tickets(self, per_page=100):
        tickets = namedtuple('tickets',['page','total_pages','data'])
        more_pages = True
        page = 0
        while more_pages:
            page += 1
            results = self.get_data('/tickets', params={
                'per_page': per_page,
                'page'    : page,
                'archived': True
            })
            
            if results['current_page'] >= results['total_pages']:
                more_pages = False
            
            yield tickets( 
                results['current_page'], 
                results['total_pages'],
                results['tickets']
            )

    def get_replies(self, ticket_id):
        data = self.get_data('/tickets/{}/replies'.format(ticket_id))
        return data['replies']
    
    def get_comments(self, ticket_id):
        data = self.get_data('/tickets/{}/comments'.format(ticket_id))
        return data['comments']
    
