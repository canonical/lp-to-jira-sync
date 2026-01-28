#####################################################################
from unittest.mock import MagicMock
from lp_to_jira_sync.lp_to_jira_sync import (
    get_bug_id, get_bug_pkg, revert_jira_status, is_lp_bug_complete
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


def test_is_lp_bug_complete_all_final():
    """Test that a bug with all tasks in final status is complete"""
    config = MagicMock()
    mock_bug = MagicMock()
    task1 = MagicMock(status="Fix Released")
    task2 = MagicMock(status="Invalid")
    task3 = MagicMock(status="Won't Fix")
    mock_bug.bug_tasks = [task1, task2, task3]
    config.lp.bugs = {12345: mock_bug}

    result = is_lp_bug_complete(config, 12345)
    assert result is True


def test_is_lp_bug_complete_some_active():
    """Test that a bug with some active tasks is not complete"""
    config = MagicMock()
    mock_bug = MagicMock()
    task1 = MagicMock(status="Fix Released")
    task2 = MagicMock(status="In Progress")
    task3 = MagicMock(status="Won't Fix")
    mock_bug.bug_tasks = [task1, task2, task3]
    config.lp.bugs = {12345: mock_bug}

    result = is_lp_bug_complete(config, 12345)
    assert result is False


def test_is_lp_bug_complete_all_active():
    """Test that a bug with all tasks active is not complete"""
    config = MagicMock()
    mock_bug = MagicMock()
    task1 = MagicMock(status="New")
    task2 = MagicMock(status="In Progress")
    task3 = MagicMock(status="Triaged")
    mock_bug.bug_tasks = [task1, task2, task3]
    config.lp.bugs = {12345: mock_bug}

    result = is_lp_bug_complete(config, 12345)
    assert result is False


def test_is_lp_bug_complete_bug_not_found():
    """Test that a bug that cannot be found returns None"""
    config = MagicMock()

    # Mock the bugs dictionary to raise an exception when accessed
    def raise_keyerror(key):
        raise KeyError("Bug not found")

    config.lp.bugs.__getitem__ = MagicMock(side_effect=raise_keyerror)

    result = is_lp_bug_complete(config, 99999)
    assert result is None


def test_is_lp_bug_complete_no_tasks():
    """Test that a bug with no tasks is considered complete"""
    config = MagicMock()
    mock_bug = MagicMock()
    mock_bug.bug_tasks = []
    config.lp.bugs = {12345: mock_bug}

    result = is_lp_bug_complete(config, 12345)
    assert result is True
