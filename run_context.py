from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jev_client import JevClient
from logged_jev import LoggedJev
from raw_logger import RawLogger

RUN_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
RUN_TIMESTAMP_LENGTH = len(datetime.min.strftime(RUN_TIMESTAMP_FORMAT))


@dataclass(frozen=True)
class RunContext:
    """What a workflow receives from whoever runs it."""

    jev: JevClient
    run_name: str
    logger: RawLogger

    def save(self, suffix: str, content: str) -> Path:
        """Write content to a file named after this run and return its path."""

        return self.logger.save(f"{self.run_name}_{suffix}", content)


@contextmanager
def start_run(workflow_name: str, logger: RawLogger) -> Iterator[RunContext]:
    """Name a new run and open a logged Jev client for it."""

    run_name = f"{workflow_name}_{datetime.now():{RUN_TIMESTAMP_FORMAT}}"
    with LoggedJev(logger, run_name) as jev:
        yield RunContext(jev, run_name, logger)


def workflow_name_of(run_name: str) -> str:
    """Strip the timestamp start_run appends. Other names come back unchanged."""

    prefix, stamp = run_name[:-RUN_TIMESTAMP_LENGTH], run_name[-RUN_TIMESTAMP_LENGTH:]
    if len(prefix) < 2 or not prefix.endswith("_"):
        return run_name
    try:
        datetime.strptime(stamp, RUN_TIMESTAMP_FORMAT)
    except ValueError:
        return run_name
    return prefix[:-1]
