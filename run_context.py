from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jev_client import JevClient
from logged_jev import LoggedJev
from raw_logger import RawLogger

RUN_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
RUN_TIMESTAMP_LENGTH = len(datetime(2000, 1, 1, tzinfo=UTC).strftime(RUN_TIMESTAMP_FORMAT))


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

    run_name = f"{workflow_name}_{datetime.now().astimezone():{RUN_TIMESTAMP_FORMAT}}"
    with LoggedJev(logger, run_name) as jev:
        yield RunContext(jev, run_name, logger)


def workflow_name_of(run_name: str) -> str:
    """Strip the timestamp start_run appends. Other names come back unchanged."""

    workflow = run_name[: -RUN_TIMESTAMP_LENGTH - 1]
    separator = run_name[-RUN_TIMESTAMP_LENGTH - 1 : -RUN_TIMESTAMP_LENGTH]
    stamp = run_name[-RUN_TIMESTAMP_LENGTH:]
    if not workflow or separator != "_":
        return run_name

    # Only the format is checked, so the missing timezone is irrelevant.

    try:
        datetime.strptime(stamp, RUN_TIMESTAMP_FORMAT)  # noqa: DTZ007
    except ValueError:
        return run_name
    return workflow
