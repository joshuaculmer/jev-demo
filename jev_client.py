from collections.abc import Mapping
from typing import Protocol

from typesafe_sdk import JSONContent, Question, SystemOneResponse


class JevClient(Protocol):
    """Anything a workflow can send System One questions to."""

    def system_one(self, state: JSONContent, questions: Mapping[str, Question]) -> SystemOneResponse: ...
