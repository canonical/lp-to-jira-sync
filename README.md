# Launchpad Bugs to Jira Issues sync

## Definitions
*LaunchPad bugs* : The bugs we are interested in here are all the bugs in
Launchpad with a specific tag that are still active in Launchpad.
These could affect any packages in the ubuntu project or individual projects
(subiquity, netplan, apport)

*Launchpad bug tasks* : each bug in Launchpad can have one or multiple tasks. A
task defines what package is affected by this bug for what series of Ubuntu. 

*active bug tasks* : In LaunchPad API (bug_task.is_complete = False)

## Specification
1. For each bug tagged, we will synchronize each affected package with ts active
tasks if the package is subscribed by a specific team
3. There could be more than one Jira ticket per Launchpad Bug
4. These Jira Bugs title will be as follows
	- LP#XXXXXX [affected package] title …….
6. The synchronization will be one-way from Launchpad to Jira
7. Launchpad will remain the Source of Truth for bug status
8. The autosync will periodically compare all the bug/package pairs in Launchpad
with all the bug/package pairs in Jira
	1. The bug is on both lists and might just need to be synced
	2. The bug is only in Launchpad and needs to either be created in Jira or resurrected if it would have been set to Done prematurely
	3. The bug is only in Jira and as a result need to be closed (Move to Done)
		1. The bug in LP could have lost its tag
		2. The bug / package tasks in LP are all complete
		3. The bug never had a tag and would need one to be in Jira
7. The auto sync will synchronize:
	1. LP title will be automatically updated in Jira
	2. The bug importance will be reflected in Jira as following
		- Uknown :  Medium
		- Undecided : Low
		- Critical : Highest
		- High : High
		- Medium : Medium
		- Low : Low
		- Wishlist : Lowest
	3. The impacted series will be sync to the jira issue as Checklist plugin items (this requires checklist to be enabled on you Jira project)
	4. If a team id mapping is provided as input, we can sync the Jira assignee with the Launchpad assignee

## Usage
```
usage: lp-to-jira-sync [-h] -p PROJECT -t TAG [-T TEAM] [-d] [-i TEAM_IDS]

A script that allows to sync bug between Lanchpad and Jira

options:
  -h, --help            show this help message and exit
  -p PROJECT, --jira-project PROJECT
                        The JIRA project string key
  -t TAG, --lp-tag TAG  The LaunchPad bug tag
  -T TEAM, --lp-team TEAM
                        The LaunchPad team with subscribed packages
  -d, --dry-run         We do not touch anything in Jira
  -i TEAM_IDS, --team-ids TEAM_IDS
                        mapping of team id between LP and Jira for assignements
```
### Examples
```
$> lp-to-jira-sync -p FB -t foundations-todo -T foundations-bugs
```

### Team mapping
It is difficult to impossible to automatically map Launchpad user with Jira assignee given they could use different emails, or id or even the Jira API may not allow to query its users for privacy. The solution is to provide a mapping of Launchpad and Jira user you want to allow mapping for as a json file and pass this file as a parameter to lp-to-jira-sync

**example.json**
``` json
{
    "bobonlp":{
        "name": "Bob Johns", "id": "634c4293de2e483e42ac1345"
    },
    "johndoeonlp":
        {"name": "John Doe", "id": "52471683e6a298a0695e1266"}
}
```
```
$> lp-to-jira-sync -p FB -t lp-tag -T lp-team -i team-mapping.json
```
