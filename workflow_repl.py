import importlib.util
from datetime import datetime
from pathlib import Path

from typesafe_sdk import TypeSafeError

from logged_jev import LoggedJev


def load_module(filename):
    path = Path(filename)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WorkflowRepl:
    def __init__(self, logger):
        self.logger = logger

    def scan_for_workflows(self, directory):
        """Return the .py files in directory that define start_workflow."""

        return [
            str(path)
            for path in sorted(Path(directory).glob("*.py"))
            if callable(getattr(load_module(path), "start_workflow", None))
        ]

    def run_workflow(self, filename):
        module = load_module(filename)
        run_name = f"{Path(filename).stem}_{datetime.now():%Y-%m-%d_%H-%M-%S}"

        with LoggedJev(self.logger, run_name) as jev:
            module.start_workflow(jev)

    def start(self, directory="workflows"):
        workflows = self.scan_for_workflows(directory)

        while True:
            print("\nWhich workflow do you want to run?")
            for i, filename in enumerate(workflows, 1):
                print(f"  {i}. {Path(filename).stem}")
            print("  q. quit")

            try:
                choice = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return

            if choice == "q":
                return
            if not (choice.isdigit() and 1 <= int(choice) <= len(workflows)):
                print(f"Enter a number from 1 to {len(workflows)}, or q.")
                continue

            try:
                self.run_workflow(workflows[int(choice) - 1])
            except KeyboardInterrupt:
                print("\nWorkflow stopped.")
            except TypeSafeError as error:
                print(f"\nTypeSafe error: {error}")
