#####################################################################
from unittest.mock import MagicMock
from lp_to_jira_sync.lp_to_jira_sync import (
    get_bug_id, get_bug_pkg, revert_jira_status, refine_tasks,
    incomplete_reason, process_issues, sync
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


# ---------------------------------------------------------------------------
# Description backfill tests
# ---------------------------------------------------------------------------

def _make_sync_issue(description=None, status="Triaged",
                     priority="Low", assignee=None, components=None):
    """Build a minimal Jira issue mock for sync() tests."""
    issue = MagicMock()
    issue.key = "FR-9999"
    issue.fields.description = description
    issue.fields.status.name = status
    issue.fields.priority.name = priority
    issue.fields.assignee = assignee
    issue.fields.components = components or []
    issue.fields.customfield_10039 = None
    return issue


def _make_sync_task(lp_description="A bug description", importance="Low"):
    task = MagicMock()
    task.bug.id = 123
    task.bug.description = lp_description
    task.bug.title = "A bug title"
    task.title = "Bug #123 in pkg (Ubuntu): A bug title"
    task.bug_target_name = "pkg (Ubuntu)"
    task.status = "New"
    task.importance = importance
    task.is_complete = False
    task.assignee_link = None
    return task


def _make_sync_config():
    config = MagicMock()
    config.team_ids = {}
    config.jira_components = []
    config.dry_run = False
    return config


def test_sync_backfills_description_when_jira_has_none():
    """Description must be written when Jira description is null."""
    issue = _make_sync_issue(description=None)
    task = _make_sync_task(lp_description="This is the LP description.")
    config = _make_sync_config()

    sync([task], issue, config)

    issue.update.assert_any_call(
        description="This is the LP description."
    )


def test_sync_does_not_overwrite_existing_description():
    """An existing Jira description must never be overwritten."""
    existing = "Manually written Jira description."
    issue = _make_sync_issue(description=existing)
    task = _make_sync_task(lp_description="A different LP description.")
    config = _make_sync_config()

    sync([task], issue, config)

    # description= must not appear in any update() call
    for call in issue.update.call_args_list:
        args, kwargs = call
        assert "description" not in kwargs, (
            "update() must not be called with description= when one exists"
        )


def test_sync_skips_backfill_when_lp_description_is_empty():
    """No update should happen if both Jira and LP descriptions are empty."""
    issue = _make_sync_issue(description=None)
    task = _make_sync_task(lp_description="")
    config = _make_sync_config()

    sync([task], issue, config)

    for call in issue.update.call_args_list:
        _, kwargs = call
        assert "description" not in kwargs


def test_sync_truncates_long_description():
    """Description longer than 32767 chars must be truncated."""
    long_desc = "x" * 40000
    issue = _make_sync_issue(description=None)
    task = _make_sync_task(lp_description=long_desc)
    config = _make_sync_config()

    sync([task], issue, config)

    for call in issue.update.call_args_list:
        _, kwargs = call
        if "description" in kwargs:
            assert len(kwargs["description"]) <= 32767
            return
    assert False, "Expected update(description=...) to be called"
