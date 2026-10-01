"""Send one workflow's request to Jev N times and log every call to outputs/scripts/.

Usage:
    python scripts/repeat_workflow.py jev_linter_files input_files/code_smell_detector/order_processor.py -n 20
    python scripts/repeat_workflow.py guessing_game -n 20
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from raw_logger import RawLogger
from run_context import start_run
from workflow_repl import load_module


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workflow", help="workflow name, e.g. jev_linter_files")
    parser.add_argument("input_path", nargs="?", help="path relative to the repo root, if the workflow takes one")
    parser.add_argument("-n", type=int, default=20, help="number of repeats (default 20)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    module = load_module(ROOT / "workflows" / f"{args.workflow}.py")
    input_path = ROOT / args.input_path if args.input_path else None
    logger = RawLogger(ROOT / "outputs" / "scripts")

    with start_run(args.workflow, logger) as context:
        for i in range(1, args.n + 1):
            module.repeatable_request(context, input_path)
            print(f"\r{i}/{args.n}", end="", flush=True)

    print(f"\nLogged {args.n} runs to {logger.log_path(context.run_name)}")


if __name__ == "__main__":
    main()
