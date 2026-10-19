from __future__ import annotations

import socket
from contextlib import contextmanager
from unittest.mock import patch


class UnexpectedExternalAccess(RuntimeError):
    """Raised when an evaluation attempts an unmocked network operation."""


def _blocked(*_args, **_kwargs):
    raise UnexpectedExternalAccess(
        "Network access is disabled in offline evaluations; patch the external boundary"
    )


@contextmanager
def block_network():
    """Fail closed on common Python socket entry points during offline trials."""
    with (
        patch.object(socket, "create_connection", _blocked),
        patch.object(socket.socket, "connect", _blocked),
        patch.object(socket.socket, "connect_ex", _blocked),
    ):
        yield
