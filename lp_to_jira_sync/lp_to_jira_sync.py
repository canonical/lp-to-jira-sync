import argparse

from lp_to_jira_sync.sync_config import SyncConfig
from jira.resources import Issue
from typing import Any


jira_priorities_mapping = {'Unknown': 'Medium',
                           'Undecided': 'Low',
                           'Critical': 'Highest',
                           'High': 'High',
                           'Medium': 'Medium',
                           'Low': 'Low',
                           'Wishlist': 'Lowest'}

Bugset = tuple[int, str]

# Create a Jira Entry from a LP bugset (list of tasks relevant to a bug and
# package)
def lp_to_jira_bug(sync_bug_id, sync_bug_tasks, config):
    """Create JIRA issue at project_id for a given Launchpad bug"""

    if is_bug_in_jira(config.jira, sync_bug_id, config.project):
        return

    lpbug = sync_bug_tasks[0].bug

    summary = 'LP#{} [{}] {}'.format(
        sync_bug_id[0], sync_bug_id[1],lpbug.title)

    # Jira API doesn't accept summary over 255 characters
    # Jira API doesn't accept description over 32767 characters
    issue_dict = {
        'project': config.project,
        'summary': summary[:255],
        'description': lpbug.description[:32767],
        'issuetype': {'name': 'Bug'}
    }

    jira_issue = config.jira.create_issue(fields=issue_dict)

    # Adding a link to the Launchpad bug into the JIRA entry
    link = {
        'url': lpbug.web_link,
        'title': 'Launchpad Link',
        'icon': {'url16x16': 'https://bugs.launchpad.net/favicon.ico'}
    }
    config.jira.add_simple_link(jira_issue, object=link)

    return jira_issue


def get_bug_id(summary):
    "Extract the bug id from a jira title which would include LP#"
    id = ""

    if summary and "LP#" in summary:
        for char in summary[summary.find("LP#")+3:]:
            if char.isdigit():
                id = id + char
            else:
                break

    return id


def get_bug_pkg(summary):
    # Extract the bug affected package from a jira title
    # which would include LP#"
    id = ""

    if summary and "LP#" in summary and '[' in summary:
        return summary[summary.index('[')+1:summary.index(']')]

    return id


def is_bug_in_jira(jira, bug_id, project_id):
    """Checks Jira for the same ID as the Bug you're trying to import"""

    request = "project = \"{}\" AND summary ~ '\"LP#{} [{}]\"'".format(
        project_id, bug_id[0], bug_id[1])

    existing_issue = jira.enhanced_search_issues(request)

    if existing_issue:
        return existing_issue[0]

    return None


# BugTask Functions
def lp_assignee(bugtasks):
    if not bugtasks:
        return None

    for task in bugtasks:
        if task.assignee_link:
            return task.assignee_link[task.assignee_link.index('~')+1:]

    return None


def lp_status(bugtasks):
    if not bugtasks:
        return None
    for task in bugtasks:
        print(task.status)

    return None


def lp_importance(bugtasks):
    if not bugtasks:
        return None
    # we return the first task importance which is the highest other than None
    return bugtasks[0].importance


def checklist(bugtasks):
    if not bugtasks:
        return None

    checklist_str = "# Default checklist"
    for task in bugtasks:
        checked = "done" if task.is_complete else "open"
        checklist_str = checklist_str + "\n* [{}] {} - {} - {}".format(
            checked,
            task.title.split(":")[0].split("in ")[1],
            task.status,
            task.importance)

    # No Checklist if only one serie impacted
    if len(bugtasks) > 1:
        return checklist_str

    return None

# return the list of taskset in the following format
# taskset is a relevant set of task for a bug/package combination
#
# {(bug_id, package):[lp tasks]}


def refine_tasks(tasks, config):
    results = {}
    for task in tasks:
        # It is much more efficient to parse the task title than accessing the
        # LP API to get the bug id
        title = task.title.split()
        name = task.bug_target_name.split()[0]

        # Create the taskset identifier
        pair = (int(title[1][1:]), name)
        if pair not in results:
            results[pair] = []

        # If package is in Ubuntu and belong to the relevant team
        if ("(Ubuntu" in task.bug_target_name
                and name in config.restricted_pkgs):
            results[pair].append(task)
        elif name in config.special_packages:
            results[pair].append(task)
        else:
            del results[pair]

    # remove bugtasks where all the task are Fix Released
    results_copy = results.copy()
    for bugtask in results:
        complete = True
        for task in results[bugtask]:
            if task.status != 'Fix Released':
                complete = False
                break
        if complete:
            del results_copy[bugtask]

    return results_copy


def find_bugs_in_jira_project(jira_api, project):
    if not jira_api or not project:
        return {}

    # Get JIRA issues in batch of 50
    issue_index = 0
    issue_batch = 50

    found_issues = {}

    request = "project = {} " \
        "AND type = Bug " \
        "AND summary ~ \"LP#\" " \
        "AND status not in (Done, \"Rejected\")""".format(project)
    issues = jira_api.enhanced_search_issues(jql_str=request)

    # For each issue in JIRA with LP# in the title
    for issue in issues:
        summary = issue.fields.summary
        lpbug_id = get_bug_id(summary)
        lppkg = get_bug_pkg(summary)

        if lpbug_id:
            found_issues[(int(lpbug_id), lppkg)] = issue

    return found_issues


def jira_assignee(issue):
    if not issue:
        return None

    return issue.fields.assignee


def jira_priority(issue):
    if not issue:
        return None

    return issue.fields.priority.name


def sync(taskset, issue, config, log_msg = ""):
    if not taskset or not issue or not config:
        return False

    bug = taskset[0].bug
    jira_comment = ""
    synced = False

    def log(msg):
        nonlocal synced
        if not synced:
            print(log_msg)
            synced = True
        print(msg)

    # Title
    # Title may change in LP and we want to make sure
    # it match the title in Jira
    # TODO: write sync title function
    jira_title = issue.fields.summary
    new_title = jira_title[:jira_title.index(']')+2] + bug.title
    
    if jira_title not in new_title:
        log("-> Syncing title for {}".format(issue.key))
        jira_comment = jira_comment + (
            ('{{lp-to-jira-sync}} Fixed out of sync title with LP: #%s\n')
            % (bug.id)
        )
        issue.update(summary=new_title[:255])

    # Status
    # At this stage at a minimum the issue should be in Triaged but other
    # status could be possible in the future Sponsoring Needed could be
    # selected if Ubuntu Sponsor team is subsribed
    # In Progress ?
    # TODO write sync status function
    if False:
        # disabling this code for now as I'm not sure it is worth it
        # it slows the execuition for all the bug and a bug might be
        # subscriobed by ubuntu sponsors for another task than the one we
        # care about
        sponsor = 'https://api.launchpad.net/devel/~ubuntu-sponsors'
        if sponsor in [x['person_link']
                       for x in bug.subscriptions.entries]:
            log(" - Fixing status to Sponsoring Needed")
            jira_comment = jira_comment + (
                ('{{lp-to-jira-sync}} ubuntu sponsors team is subscribed '
                 'to the bug which means it should move to Sponsoring '
                 'Needed')
            )
            config.jira.transition_issue(
                issue,
                transition='Sponsoring Needed'
            )

    # sync Status
    if issue.fields.status.name == 'Untriaged':
        log("-> Updating Status for {} to Triaged".format(issue.key))
        jira_comment = jira_comment + (
           ('{{lp-to-jira-sync}} %s should be Triaged\n') % (config.tag)
        )
        config.jira.transition_issue(
            issue,
            transition='Triaged'
        )

    # Sync Checklist
    # If a bug impact a package on multiple serie, we create a Checklist on the
    # Jira issue that list all series
    checkstr = checklist(taskset)
    jiracheckstr = issue.fields.customfield_10039
    if checkstr and checkstr != jiracheckstr:
        log("-> Updating Checklist for {}".format(issue.key))
        issue.update(fields={'customfield_10039': checkstr})
        jira_comment = jira_comment + (
            ('{{lp-to-jira-sync}} Updating Checklist according to LP: #%s\n')
            % (bug.id)
        )

    # Assignee
    # If a team mapping has been provided we can look at for a match between
    # The LaunchPad bug assignee and the Jira account available
    # TODO create a standalone function for assignee actions
    if config.team_ids:
        lp_who = lp_assignee(taskset)
        jira_who = jira_assignee(issue)
        if lp_who in config.team_ids.keys():
            # Someone from specific team is assigned to the bug
            # But nobody is assigned in Jira
            # In that case we assign the bug the same person from LP
            if not jira_who:
                account = config.team_ids[lp_who]['id']
                issue.update(assignee={'id': account})
                log("-> Updating assignee for {} to {}".format(
                    issue.key,
                    config.team_ids[lp_who]['name']))
                jira_comment = jira_comment + (
                    ('{{lp-to-jira-sync}} Updating Assignee according to '
                     'LP: #%s\n') % (bug.id)
                )

    # Importance
    # We should reflect the launchpad bug Priority with the Jira issue priority
    importance = jira_priorities_mapping[lp_importance(taskset)]
    priority = jira_priority(issue)
    if importance != priority:
        log("-> Syncing Priority for {} to {}".format(
            issue.key, importance))
        issue.update(priority={"name": importance})
        jira_comment = jira_comment + (
            ('{{lp-to-jira-sync}} Updating Priority according to LP: #%s\n')
            % (bug.id)
        )

    # Sync Jira Component with Package in Launchpad if mapping available
    if config.jira_components:
        pkg_name = taskset[0].title.split()[3]
        # remove sneaky trailing ':'
        if pkg_name[-1] == ':':
            pkg_name = pkg_name[:-1]
        # Retrieve the proper LP component
        component = config.package_to_component(pkg_name)
        # Retrieve the Jira components if any
        issue_components = [x.name for x in issue.fields.components]

        # If there is a LaunchPad component and it isn't already set in Jira
        # and is an available Component on the Jira project
        if (
            component and
            component not in issue_components and
            component in config.jira_components
        ):
            log("-> Updating Components for {} to {}"
                  .format(issue.key, component))
            issue.update(fields={"components": []})
            issue.update(
                update={"components": [{"add": {"name": component, }}], }, )
            jira_comment = jira_comment + (
                ('{{lp-to-jira-sync}} Updating Component according to '
                 'LP: #%s\n') % (bug.id)
            )

    if jira_comment:
        config.jira.add_comment(issue, jira_comment)

def revert_jira_status(config: SyncConfig, jira_issue: Issue, tasks: list):
    not_progressing = (t for t in tasks if t.status in (
        'New',
        'Confirmed',
        'Incomplete',
        'Triaged'
        ))
    if not any(not_progressing):
        print(f"Not reverting status for {jira_issue.key} since all LP task are progressing.")
        return

    comment = (
        '{{lp-to-jira-sync}} This Bug is still active and tagged '
        '%s in LP. It wil be moved to the Backlog as Triaged. '
        'If no work is necessary or the bug isn\'t relevant '
        'anymore, please untag the bug in LP.') % (config.tag)
    if not config.dry_run:
        config.jira.transition_issue(
            jira_issue,
            transition='Triaged'
        )
        config.jira.add_comment(jira_issue, comment)


def process_issues(all_tasks: dict[Bugset, list], all_issues: dict[Bugset, Issue], config):
    # Between All subscribed bug in LP and all bug imported in JIRA, there's
    # 3 Groups:
    #   A: bug are active in both LP and Jira
    #   B: bugs only active in LP
    #   C: bugs only active in Jira

    # an active bug in Jira has a status different than Done or Rejected
    # an active bug in LP is not Fix Released and Invalid

    # Group A
    #   -> Check if they are in sync

    # Group B
    #   -> Add them to JIRA, and sync

    # Group C
    #   Could have been unsubscribed in LP, or added in JIRA and multiple
    #   actions are possible
    #   For now we will go the hard way and REJECT any bug in Jira that isn't
    #   tagged

    for bugset in all_tasks:
        if bugset in all_issues:
            # bug are active in both LP and Jira
            log_msg = ("LP-Jira: LP: #{} [{}] is in Jira as {}"
                  .format(bugset[0], bugset[1], all_issues[bugset].key))
            if not config.dry_run:
                sync(
                    all_tasks[bugset],
                    all_issues[bugset],
                    config,
                    log_msg)
            del all_issues[bugset]
        else:
            # bugs only active in LP
            log_msg = ("LP Only: LP: #{} [{}] is not active in Jira"
                  .format(bugset[0], bugset[1]))

            # Checking if the bug is inactive in Jira
            jira_issue = is_bug_in_jira(config.jira, bugset, config.project)
            if jira_issue and str(jira_issue.fields.status) in ('Done', 'Rejected'):
                revert_jira_status(config, jira_issue, all_tasks[bugset])
            else:
                if not config.dry_run:
                    jira_issue = lp_to_jira_bug(
                                    bugset, all_tasks[bugset], config)
                else:
                    pass

            if not config.dry_run:
                sync(
                    all_tasks[bugset],
                    jira_issue,
                    config,
                    log_msg)

    for issue in all_issues:
        # bugs only active in Jira
        print((
                'Jira Only: LP: #{} [{}] is in Jira as {} but not tagged or '
                'active in LP').format(
            issue[0], issue[1],  all_issues[issue].key))
        comment = (
            '{{lp-to-jira-sync}} LP: #%s is either not tagged %s or active at '
            'this time. Moving issue to Done. If this is incorrect, check the '
            'status of the bug in LaunchPad.') % (issue[0], config.tag)
        if not config.dry_run:
            config.jira.transition_issue(all_issues[issue], transition="Done")
            config.jira.add_comment(all_issues[issue], comment)


def main(args=None):
    parser = argparse.ArgumentParser(
        description='A script that allows to sync bug between Lanchpad '
                    'and Jira'
    )
    parser.add_argument(
        '-p',
        '--jira-project',
        required=True,
        dest='project', type=str,
        help="The JIRA project string key")
    parser.add_argument(
        '-t',
        '--lp-tag',
        required=True,
        dest='tag', type=str,
        help='The LaunchPad bug tag')
    parser.add_argument(
        '-T',
        '--lp-team',
        dest='team', type=str,
        help='The LaunchPad team with subscribed packages')
    parser.add_argument(
        '-d',
        '--dry-run',
        dest='dry_run',
        action='store_true',
        help='We do not touch anything in Jira')
    parser.add_argument(
        '-i',
        '--team-ids',
        dest='team_ids',
        type=str,
        help='mapping of team id between LP and Jira for assignements')

    parser.add_argument(
        '-c',
        '--components-mapping',
        dest='components_mapping',
        type=str,
        help='mapping of Jira Components to Launchpad packages')

    parser.add_argument(
        '-j',
        '--jira-token',
        dest='jira_token',
        type=str,
        help='specify a jira token file other than the default ~/.jira.token')

    opts = parser.parse_args(args)

    config = SyncConfig(
        project=opts.project,
        lp_tag=opts.tag,
        lp_team=opts.team,
        # TODO : Special packages should be a configuration option
        special_packages=['subiquity', 'netplan', 'apport', 'ubuntu-cdimage'],
        dry_run=opts.dry_run,
        team_ids_json=opts.team_ids,
        packages_mapping_json=opts.components_mapping,
        jira_token=opts.jira_token
        )

    print("Found {} subscribed packages by team {}"
          .format(len(config.restricted_pkgs), config.team))

    print("Retrieving all tasks from bug with {} tag".format(config.tag))
    statuses = ['Triaged',
                'Fix Committed',
                'New',
                'In Progress',
                'Incomplete',
                'Confirmed',
                'Fix Released']

    # TODO searchTasks could return lazr.restfulclient.errors.ServerError:
    # HTTP Error 503: Service Unavailable, Should probably catch this exception
    tasks = config.lp.bugs.searchTasks(tags=config.tag, status=statuses)
    print(" - Found {} bug's task{} in LaunchPad".format(
        len(tasks), "s" if len(tasks) > 1 else "")
    )

    # Remove tasks that affects non ubscribed ackages
    refined_tasks = refine_tasks(tasks, config)

    print(" - Found {} valid bug's task{}".format(
        len(refined_tasks), "s" if len(refined_tasks) > 1 else "")
    )

    # Create a set of all active Jira issues
    print("Retrieving all the imported LP Tasks in Jira")
    all_issues = find_bugs_in_jira_project(config.jira, config.project)
    print(" - Found {} issue{} in JIRA".format(
        len(all_issues), "s" if len(all_issues) > 1 else "")
    )

    process_issues(refined_tasks, all_issues, config)

# =============================================================================
