"""Logging rules shared by the API and the worker."""

import logging

# HTTP client libraries log full request URLs at INFO, which would reveal which job boards the
# user follows. Keep them to warnings; our own log lines record what is needed without content.
QUIET_LOGGERS = ("httpx", "httpcore")


def quiet_third_party_loggers() -> None:
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
