import importlib.util
from pathlib import Path

from typesafe_sdk import TypeSafeError

from run_context import start_run


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

        with start_run(Path(filename).stem, self.logger) as context:
            module.start_workflow(context)

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
