#!/usr/bin/python3
# This object provide an easy way to acces your local jira tokens or guide
# you through the process to get them and store them for future use

import os
import json


attlassian = "https://id.atlassian.com/manage-profile/security/api-tokens"


class jira_config():
    def __init__(self,
                 credstore="{}/.jira.token".format(os.path.expanduser('~'))):
        snap_home = os.getenv("SNAP_USER_COMMON")

        if snap_home:
            self.credstore = "{}/.jira.token".format(snap_home)
        else:
            self.credstore = credstore
        try:
            with open(self.credstore) as f:
                config = json.load(f)
                self.server = config['jira-server']
                self.login = config['jira-login']
                self.token = config['jira-token']
        except (FileNotFoundError, json.JSONDecodeError):
            print('JIRA Token file {} could not be found or parsed.'
                  .format(self.credstore))
            print('')
            gather_token = input(
                'Do you want to enter your JIRA token information now? (Y/n) ')
            if gather_token == 'n':
                raise ValueError("JIRA API isn't initialized")
            self.server = input('Please enter your jira server address : ')
            self.login = input('Please enter your email login for JIRA : ')
            self.token = input('Please enter your JIRA API Token '
                               '(see {}) : '.format(attlassian))
            save_token = input('Do you want to save those credentials for '
                               'future use ? (Y/n) ')
            if save_token != 'n':
                try:
                    data = {}
                    data['jira-server'] = self.server
                    data['jira-login'] = self.login
                    data['jira-token'] = self.token
                    with open(self.credstore, 'w+') as f:
                        json.dump(data, f)
                except (FileNotFoundError, json.JSONDecodeError):
                    raise ValueError("JIRA API isn't initialized")
