"""Send one workflow's request to Jev N times and log every call to outputs/scripts/.

Usage:
    python scripts/repeat_workflow.py code_smell_detector order_processor.py -n 20
    python scripts/repeat_workflow.py guessing_game -n 20
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from logged_jev import LoggedJev
from raw_logger import RawLogger
from workflow_repl import load_module


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("workflow", help="workflow name, e.g. code_smell_detector")
    parser.add_argument("input_file", nargs="?", help="file name in input_files/<workflow>/, if the workflow takes one")
    parser.add_argument("-n", type=int, default=20, help="number of repeats (default 20)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    module = load_module(ROOT / "workflows" / f"{args.workflow}.py")
    input_path = ROOT / "input_files" / args.workflow / args.input_file if args.input_file else None

    run_name = f"{args.workflow}_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    logger = RawLogger(ROOT / "outputs" / "scripts")

    with LoggedJev(logger, run_name) as jev:
        for i in range(1, args.n + 1):
            module.repeatable_request(jev, input_path)
            print(f"\r{i}/{args.n}", end="", flush=True)

    print(f"\nLogged {args.n} calls to outputs/scripts/{run_name}.txt")


if __name__ == "__main__":
    main()
