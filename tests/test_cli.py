import sys
from contextlib import contextmanager
from typing import List
from unittest.mock import patch

import pytest

from via_patterns.__main__ import app


class ExitTest(Exception):
    pass


@pytest.fixture
def cli_isolation(monkeypatch):
    def mock_exit(*args, **kwargs):
        raise ExitTest(*args, **kwargs)

    monkeypatch.setattr("sys.exit", mock_exit)

    @contextmanager
    def _isolation(args: List):
        args.insert(0, "")
        with patch.object(sys, "argv", args):
            yield

    yield _isolation


@pytest.mark.parametrize("arguments", [[], ["are", "ignored"]])
def test_cli_arguments(arguments, cli_isolation, caplog) -> None:
    with cli_isolation(arguments):
        with pytest.raises(ExitTest):
            app()

    assert (
        caplog.records[0].message
        == "This plugin is not usable when running as python module"
    )
