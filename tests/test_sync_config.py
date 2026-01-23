import pytest
from unittest.mock import patch, MagicMock
from lp_to_jira_sync.sync_config import SyncConfig


@patch('lp_to_jira_sync.sync_config.JIRA')
@patch('lp_to_jira_sync.sync_config.jira_config')
def test_init_without_jira_api(mock_jira_config, mock_jira):
    mock_jira.side_effect = ValueError("No Jira")
    with pytest.raises(ValueError) as e:
        SyncConfig()

    assert str(e.value) == "ERROR: Cannot initialize Jira API"


@patch('lp_to_jira_sync.sync_config.Launchpad')
@patch('lp_to_jira_sync.sync_config.jira_config')
def test_init_with_jira_and_lp(mock_launchpad, mock_jira_config):
    mock_jira = MagicMock()
    mock_jira_config.return_value = MagicMock(jira=mock_jira)

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    config = SyncConfig(jira=mock_jira, lp_api=mock_lp, project='TEST_PROJECT')

    assert config.jira == mock_jira
    assert config.project == 'TEST_PROJECT'
    assert config.lp == mock_lp
    assert config.tag == ''
    assert config.team == ''
    assert config.restricted_pkgs == []
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None


@patch('lp_to_jira_sync.sync_config.Launchpad')
@patch('lp_to_jira_sync.sync_config.jira_config')
@patch('lp_to_jira_sync.sync_config.JIRA')
def test_init_with_jira_config(mock_jira, mock_jira_config, mock_launchpad):
    # Create a mock Jira Config
    mock_jira_config_instance = MagicMock()
    # Set the return value of the mocked jira_config function
    mock_jira_config.return_value = MagicMock(jira=mock_jira_config_instance)

    # Create a mock Jira instance
    mock_jira_instance = MagicMock()

    # Set the return value of the mocked jira_config function
    mock_jira.return_value = mock_jira_instance

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    # Create a SyncConfig instance
    config = SyncConfig(project='TEST_PROJECT')

    # Verify the attributes of the SyncConfig instance
    assert config.jira == mock_jira_instance
    assert config.project == 'TEST_PROJECT'
    assert config.lp is not None
    assert config.tag == ''
    assert config.team == ''
    assert config.restricted_pkgs == []
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None


@patch('lp_to_jira_sync.sync_config.requests')
@patch('lp_to_jira_sync.sync_config.jira_config')
@patch('lp_to_jira_sync.sync_config.Launchpad')
def test_init_with_lp_team(mock_launchpad, mock_jira_config, mock_requests):
    mock_jira = MagicMock()
    mock_jira_config.return_value = MagicMock(jira=mock_jira)

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    pkg1 = MagicMock()
    pkg1.configure_mock(name='pkg1')

    pkg2 = MagicMock()
    pkg2.configure_mock(name='pkg2')

    (mock_lp.people.__getitem__.return_value
        .getBugSubscriberPackages.return_value) = [pkg1, pkg2]

    # We will skip the json download at this time
    mock_requests = MagicMock()
    mock_requests.get.return_value = 404

    config = SyncConfig(jira=mock_jira,
                        lp_api=mock_lp,
                        project='TEST_PROJECT',
                        lp_team='test_team')

    assert config.jira == mock_jira
    assert config.project == 'TEST_PROJECT'
    assert config.lp == mock_lp
    assert config.tag == ''
    assert config.team == 'test_team'
    assert config.restricted_pkgs == ['pkg1', 'pkg2']
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None


@patch('lp_to_jira_sync.sync_config.requests')
@patch('lp_to_jira_sync.sync_config.jira_config')
@patch('lp_to_jira_sync.sync_config.Launchpad')
def test_init_with_lp_team_and_json(
        mock_launchpad, mock_jira_config, mock_requests):
    mock_jira = MagicMock()
    mock_jira_config.return_value = MagicMock(jira=mock_jira)

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    pkg_data = {
        "team_a": ["pkg_a", "pkg_b"],
        "team_b": ["pkg_c", "pkg_d"]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = pkg_data

    # We will skip the json download at this time
    mock_requests.get.return_value = mock_response

    config = SyncConfig(jira=mock_jira,
                        lp_api=mock_lp,
                        project='TEST_PROJECT',
                        lp_team='team_a')

    assert config.jira == mock_jira
    assert config.project == 'TEST_PROJECT'
    assert config.lp == mock_lp
    assert config.tag == ''
    assert config.team == 'team_a'
    assert config.restricted_pkgs == ['pkg_a', 'pkg_b']
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None
    assert config.team_ids == []


@patch('lp_to_jira_sync.sync_config.json')
@patch('lp_to_jira_sync.sync_config.open')
@patch('lp_to_jira_sync.sync_config.Launchpad')
@patch('lp_to_jira_sync.sync_config.jira_config')
def test_init_with_team_mapping(mock_launchpad,
                                mock_jira_config,
                                mock_open,
                                mock_json):
    mock_jira = MagicMock()
    mock_jira_config.return_value = MagicMock(jira=mock_jira)

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    team_mapping = {
        "bob": {"name": "Bobby", "id": "123456789"},
        "ben": {"name": "Bernard", "id": "987654321"}
    }
    mock_json.load.return_value = team_mapping

    config = SyncConfig(
        jira=mock_jira,
        lp_api=mock_lp,
        project='TEST_PROJECT',
        team_ids_json="team_ids.json")

    assert config.jira == mock_jira
    assert config.project == 'TEST_PROJECT'
    assert config.lp == mock_lp
    assert config.tag == ''
    assert config.team == ''
    assert config.restricted_pkgs == []
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None
    assert config.team_ids["bob"]["name"] == "Bobby"
    assert config.team_ids["ben"]["id"] == "987654321"
    mock_open.assert_called_once_with('team_ids.json')


@patch('lp_to_jira_sync.sync_config.json')
@patch('lp_to_jira_sync.sync_config.open')
@patch('lp_to_jira_sync.sync_config.Launchpad')
@patch('lp_to_jira_sync.sync_config.jira_config')
def test_init_with_component_mapping(mock_launchpad,
                                     mock_jira_config,
                                     mock_open,
                                     mock_json):
    mock_jira = MagicMock()
    mock_jira_config.return_value = MagicMock(jira=mock_jira)

    mock_lp = MagicMock()
    mock_launchpad.login_with.return_value = mock_lp

    component_mapping = {
        "boot": ["grub2", "shim", "u-boot"],
        "crypto": ["openssl", "openssh", "cryptsetup"]
    }
    mock_json.load.return_value = component_mapping

    config = SyncConfig(
        jira=mock_jira,
        lp_api=mock_lp,
        project='TEST_PROJECT',
        packages_mapping_json="ids.json")

    assert config.jira == mock_jira
    assert config.project == 'TEST_PROJECT'
    assert config.lp == mock_lp
    assert config.tag == ''
    assert config.team == ''
    assert config.restricted_pkgs == []
    assert config.special_packages == []
    assert config.dry_run is True
    assert config.args is None
    assert "grub2" in config.components_ids["boot"]
    assert "shim" in config.components_ids["boot"]
    assert "openssl" in config.components_ids["crypto"]

    mock_open.assert_called_once_with('ids.json')
