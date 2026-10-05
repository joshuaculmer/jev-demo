"""What filters report while they run: progress for the operator and token usage for the report."""

from collections.abc import Mapping
from typing import Protocol

from typesafe_sdk import JSONContent, Question, SystemOneResponse

from jev_client import JevClient
from jev_linter.findings import FilterResult, Usage


class Progress(Protocol):
    def start(self, source: str, total: int) -> None: ...

    def note(self, text: str) -> None: ...

    def step(self, label: str) -> None: ...

    def finish(self, result: FilterResult) -> None: ...


class SilentProgress:
    """The default for filters called from scripts."""

    def start(self, source: str, total: int) -> None:
        pass

    def note(self, text: str) -> None:
        pass

    def step(self, label: str) -> None:
        pass

    def finish(self, result: FilterResult) -> None:
        pass


SILENT_PROGRESS = SilentProgress()


class UsageCounter:
    """A JevClient that forwards each request and adds its token usage to a running total."""

    def __init__(self, jev: JevClient) -> None:
        self.jev = jev
        self.usage = Usage()

    def system_one(self, state: JSONContent, questions: Mapping[str, Question]) -> SystemOneResponse:
        response = self.jev.system_one(state, questions)
        tokens = response.usage
        self.usage += Usage(1, tokens.input_tokens or 0, tokens.output_tokens or 0)
        return response
