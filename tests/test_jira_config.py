#####################################################################
import pytest
import json
from unittest.mock import patch, MagicMock
from io import StringIO
from lp_to_jira_sync.jira_config import jira_config


def test_init_with_existing_token_file():
    # Mock the content of the token file
    token_data = {
        'jira-server': 'https://example.atlassian.net',
        'jira-login': 'test@example.com',
        'jira-token': 'api-token'
    }
    with patch('builtins.open', return_value=StringIO(json.dumps(token_data))):
        config = jira_config()

    # Verify that the configuration is loaded correctly
    assert config.server == 'https://example.atlassian.net'
    assert config.login == 'test@example.com'
    assert config.token == 'api-token'


@patch('builtins.input')
@patch('builtins.open', side_effect=[FileNotFoundError, None])
def test_init_with_missing_token_file_without_saving(mock_open, mock_input):
    mock_input.side_effect = ['y',
                              'https://example.atlassian.net',
                              'test@example.com',
                              'api-token',
                              'n']  # without saving

    config = jira_config()

    # Verify that the user is prompted for input
    assert config.server == 'https://example.atlassian.net'
    assert config.login == 'test@example.com'
    assert config.token == 'api-token'


@patch('builtins.input')
@patch('builtins.open', side_effect=[FileNotFoundError, None])
def test_init_with_snap_home(mock_open, mock_input):
    # Simulate initialization when SNAP_USER_COMMON is set
    # If set the test will use the mock location and won't find the file
    # It will then prompt for user input and will trigger the input mocks
    mock_input.side_effect = ['y',
                              'https://example.atlassian.net',
                              'test@example.com',
                              'api-token',
                              'n']  # without saving
    with patch.dict('os.environ', {'SNAP_USER_COMMON': '/mocked/snap_home'}):
        config = jira_config()
    assert config.credstore == '/mocked/snap_home/.jira.token'
    # Verify that the user is prompted for input
    assert config.server == 'https://example.atlassian.net'
    assert config.login == 'test@example.com'
    assert config.token == 'api-token'


@patch('builtins.input')
@patch('builtins.open', side_effect=[FileNotFoundError])
def test_init_with_missing_token_file_and_no_api_input(mock_open, mock_input):
    mock_input.side_effect = ['n',
                              'https://example.atlassian.net',
                              'test@example.com',
                              'api-token',
                              'n']
    with pytest.raises(ValueError):
        jira_config()

    # Verify user is prompted for input but the configuration is not saved
    mock_input.assert_called_with('Do you want to enter your JIRA token'
                                  ' information now? (Y/n) ')


@patch('builtins.input')
@patch('builtins.open', side_effect=[FileNotFoundError, MagicMock()])
def test_init_with_missing_token_file_with_saving(mock_open, mock_input):
    mock_input.side_effect = ['y',
                              'https://example.atlassian.net',
                              'test@example.com',
                              'api-token',
                              'Y']

    config = jira_config()

    # Verify that the user is prompted for input
    assert config.server == 'https://example.atlassian.net'
    assert config.login == 'test@example.com'
    assert config.token == 'api-token'


@patch('builtins.input')
@patch('builtins.open', side_effect=[FileNotFoundError, FileNotFoundError])
def test_init_with_missing_token_file_with_saving_failure(mock_open,
                                                          mock_input):
    mock_input.side_effect = ['y',
                              'https://example.atlassian.net',
                              'test@example.com',
                              'api-token',
                              'Y']
    with pytest.raises(ValueError):
        jira_config()
