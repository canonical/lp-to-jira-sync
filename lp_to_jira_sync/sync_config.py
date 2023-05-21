from jira import JIRA
import requests
import json

from launchpadlib.launchpad import Launchpad

from lp_to_jira_sync.jira_config import jira_config

teampkgs =\
    'https://reqorts.qa.ubuntu.com/reports/m-r-package-team-mapping.json'


class SyncConfig:
    def __init__(self,
                 jira=None,
                 project="",
                 lp_api=None,
                 lp_tag="",
                 lp_team="",
                 team_ids_json="",
                 special_packages=[],
                 dry_run=True,
                 args=None):

        if not jira:
            try:
                print("initializing Jira API ....")
                jira_cfg = jira_config()
                self.jira = JIRA(
                    jira_cfg.server,
                    basic_auth=(jira_cfg.login, jira_cfg.token))
            except ValueError as e:
                raise ValueError("ERROR: Cannot initialize Jira API") from e
        else:
            self.jira = jira

        self.project = project

        if not lp_api:
            print("initializing LaunchPad API ....")
            self.lp = Launchpad.login_with(
                'lp-subscribed-bugs', 'production', version='devel'
            )
        else:
            self.lp = lp_api

        self.tag = lp_tag

        self.team = lp_team

        self.restricted_pkgs = []

        # buildind a list of restricted packages for the selected team
        if lp_team:
            print("Building list of restricted packages ....")
            # First we wil try to download the team mapping which is faster
            response = requests.get(teampkgs)
            if response.status_code == 200:
                json_data = response.json()
                self.restricted_pkgs = json_data[lp_team]
            # If it fails for any reason, we go the hard way to get it from LP
            if not self.restricted_pkgs:
                pkgs = self.lp.people[self.team].getBugSubscriberPackages()
                self.restricted_pkgs = [pkg.name for pkg in pkgs]

        self.team_ids = []
        if team_ids_json:
            with open(team_ids_json) as file:
                self.team_ids = json.load(file)

        self.special_packages = special_packages

        self.dry_run = dry_run

        self.args = args
