"""Shared pytest fixtures and hooks."""

import logging

import pytest


@pytest.fixture(autouse=True)
def clean_mcprojsim_logger() -> None:
    """Clear mcprojsim logger handlers before each test.

    CLI tests invoke setup_logging() through Click's CliRunner.  CliRunner
    temporarily replaces sys.stdout with a closed buffer; setup_logging()
    captures that buffer in a StreamHandler.  When the invocation finishes the
    buffer is closed, but the handler persists on the module-level logger
    (protected by the ``if not logger.handlers`` guard).  Any subsequent test
    in the same xdist worker that emits a log record propagating to the
    mcprojsim logger will attempt to write to the closed buffer and raise
    ``ValueError: I/O operation on closed file``.

    Clearing handlers *before* each test ensures every test starts with no
    stale stream references regardless of execution order.
    """
    logging.getLogger("mcprojsim").handlers.clear()
