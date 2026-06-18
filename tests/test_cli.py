from unittest.mock import patch

from via_patterns.__main__ import app


def test_app_delegates_to_plugin_action() -> None:
    with patch("via_patterns.__main__.PluginAction") as mock_plugin_action:
        app()

    mock_plugin_action.assert_called_once_with()
    mock_plugin_action.return_value.run.assert_called_once_with()
