"""Preflight local browser-test permissions without starting a GUI process."""

import socket


def check_local_test_ports():
    # E2E requires loopback listeners. In restricted macOS agent environments,
    # checking this first avoids launching Chrome into the known failing context.
    # This is a necessary permission check, not proof that GUI launch is allowed.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
