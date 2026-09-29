from dotenv import load_dotenv

from raw_logger import RawLogger
from workflow_repl import WorkflowRepl

load_dotenv()

logger = RawLogger("outputs")
repl = WorkflowRepl(logger)
repl.start()
