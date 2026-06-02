"""Smoke checks for replay harness I/O seals."""

import socket
import urllib.request

import pytest


def test_daemon_factory_wires_fakes(
    daemon_factory,
    fake_router,
    fake_cake_reader,
):
    daemon = daemon_factory()
    assert daemon.router is fake_router
    assert daemon.cake_reader is fake_cake_reader
    assert fake_router.assert_only_documented_calls() is None


def test_urlopen_seal_raises():
    with pytest.raises(RuntimeError, match="no HTTP calls allowed"):
        urllib.request.urlopen("http://127.0.0.1/")


def test_socket_seal_raises():
    sock = socket.socket()
    with pytest.raises(RuntimeError, match="no socket calls allowed"):
        sock.connect(("127.0.0.1", 9))
