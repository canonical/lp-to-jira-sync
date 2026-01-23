#####################################################################
from unittest.mock import MagicMock
from lp_to_jira_sync.lp_to_jira_sync import (
    get_bug_id, get_bug_pkg, revert_jira_status
)


def test_get_bug_id():
    assert get_bug_id(None) == ""
    assert get_bug_id("") == ""
    assert get_bug_id("This isn't the right title") == ""
    assert get_bug_id("LP#123234") == "123234"
    assert get_bug_id("LP#123234 [busybox] There is a problemm") == "123234"
    assert get_bug_id("LP# 123234 [busybox] There is a problemm") == ""
    review_title = "Review LP#123234 [busybox] There is a problemm"
    assert get_bug_id(review_title) == "123234"


def test_get_bug_pkg():
    assert get_bug_pkg(None) == ""
    assert get_bug_pkg("") == ""
    assert get_bug_pkg("This isn't the right title") == ""
    assert get_bug_pkg("LP#123234") == ""
    assert get_bug_pkg("LP#123234 [busybox] There is a problemm") == "busybox"
    assert get_bug_pkg("LP# 123234 [busybox] There is a problemm") == "busybox"


def test_no_revert_while_in_sru_queue():
    config = MagicMock(tag="bogus-tag", dry_run=False)
    tasks = [
        MagicMock(status="Fix Released"),  # already fixed on devel series
        MagicMock(status="In Progress"),  # SRU in queue for last stable
        MagicMock(status="Won't Fix"),  # Not fixing almost EOL interim
        MagicMock(status="In Progress"),  # SRU in queue for last LTS
    ]
    issue = MagicMock(id="FR-1234")

    revert_jira_status(config, issue, tasks)
    config.jira.transition_issue.assert_not_called()


def test_revert_bug_reopened():
    config = MagicMock(tag="bogus-tag", dry_run=False)
    tasks = [
        MagicMock(status="Confirmed"),  # Whoops, the devel fix didn't work!
        MagicMock(status="In Progress"),  # SRU in queue for last stable
        MagicMock(status="Won't Fix"),  # Not fixing almost EOL interim
        MagicMock(status="In Progress"),  # SRU in queue for last LTS
    ]
    issue = MagicMock(id="FR-1234")

    revert_jira_status(config, issue, tasks)
    config.jira.transition_issue.assert_called_with(issue, transition='Triaged')
