#####################################################################
from unittest.mock import MagicMock
from lp_to_jira_sync.lp_to_jira_sync import (
    get_bug_id, get_bug_pkg, revert_jira_status, refine_tasks,
    incomplete_reason, process_issues
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


def test_refine_tasks_keeps_pair_with_later_ineligible_task():
    # LP#1957863: an ineligible upstream task must not wipe the eligible
    # Ubuntu package task pair from the results.
    config = MagicMock(
        restricted_pkgs=["update-notifier"],
        special_packages=[])
    ubuntu_task = MagicMock(
        title="Bug #1957863 in update-notifier (Ubuntu): coding errors",
        bug_target_name="update-notifier (Ubuntu)",
        status="New")
    upstream_task = MagicMock(
        title="Bug #1957863 in update-notifier: coding errors",
        bug_target_name="update-notifier",
        status="New")

    results = refine_tasks([ubuntu_task, upstream_task], config)

    pair = (1957863, "update-notifier")
    assert pair in results
    assert results[pair]


def _make_issue(bug_id=1957863, pkg="update-notifier"):
    issue = MagicMock()
    issue.fields.summary = "LP#{} [{}] A bug title".format(bug_id, pkg)
    return issue


def _make_bug(tasks, tags=("foundations-todo",)):
    bug = MagicMock()
    bug.bug_tasks = tasks
    bug.tags = list(tags)
    return bug


def _eligible_tasks():
    return [
        MagicMock(bug_target_name="update-notifier (Ubuntu)",
                  status="New",
                  is_complete=False),
        MagicMock(bug_target_name="update-notifier (Ubuntu)",
                  status="In Progress",
                  is_complete=False),
    ]


def test_incomplete_reason_missing_tag():
    bug = _make_bug(_eligible_tasks(), tags=("other-tag",))
    assert incomplete_reason(bug, "foundations-todo") == \
        "missing tag 'foundations-todo'"


def test_incomplete_reason_no_eligible_tasks():
    task = MagicMock(bug_target_name="update-notifier",
                     status="New", is_complete=False)
    bug = _make_bug([task], tags=("foundations-todo",))
    assert incomplete_reason(bug, "foundations-todo") == \
        "no eligible LP task (not an Ubuntu package task)"


def test_incomplete_reason_all_complete():
    tasks = [
        MagicMock(bug_target_name="update-notifier (Ubuntu)",
                  status="Fix Released", is_complete=True),
    ]
    bug = _make_bug(tasks, tags=("foundations-todo",))
    assert incomplete_reason(bug, "foundations-todo") == \
        "all LP tasks marked complete"


def test_incomplete_reason_bug_missing():
    assert incomplete_reason(None, "foundations-todo") == \
        "bug not accessible in Launchpad"


def test_jira_only_close_comment_includes_specific_reason():
    config = MagicMock(tag="foundations-todo", dry_run=False)
    jira_issue = _make_issue(1957863, "update-notifier")
    all_issues = {(1957863, "update-notifier"): jira_issue}

    lp_bug = _make_bug(
        [MagicMock(bug_target_name="update-notifier (Ubuntu)",
                   status="Fix Released", is_complete=True)],
        tags=("foundations-todo",))
    (config.lp.bugs.__getitem__.return_value) = lp_bug

    process_issues({}, all_issues, config)

    comment = config.jira.add_comment.call_args[0][1]
    assert "all LP tasks marked complete" in comment
    assert "not tagged or active in LP" not in comment
    assert config.jira.transition_issue.called
