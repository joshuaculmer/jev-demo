# jev-demo

A small harness for building and testing workflows on [TypeSafe](https://docs.typesafe.ai)'s Jev model.

Each workflow is a plain Python module. An interactive menu runs workflows one at a time. Every call to Jev gets logged, and two scripts repeat a request many times and chart how much the answers vary.

The largest workflow family is `jev_linter`, a code-smell linter for Python projects. Ruff handles the rules a deterministic linter can check. Jev then judges the smells that need semantic understanding, first inside each function and then across the whole project.

## Setup

Requires Python 3.13 (tested with `typesafe-sdk` 0.7.2 and `ruff` 0.16).

```sh
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
TYPESAFE_API_KEY=your-key-here
```

## Running workflows

```sh
python main.py
```

Run it from the project root. The menu lists every workflow in `workflows/`. Pick one by number, or enter `q` to quit. `Ctrl+C` stops the current workflow and returns to the menu.

Each run appends the raw JSON of every request and response to `outputs/<workflow>_<timestamp>.txt`. Workflows can save other files under the same run name, such as the linter's `outputs/<workflow>_<timestamp>_findings.json`.

## Included workflows

| Workflow | Primitives | What it does |
| --- | --- | --- |
| `guessing_game` | `Choice` | Jev picks a number from 1 to 100 and grades each guess as higher, lower, or match |
| `prompt_injection_detection` | `Noul` + 2 × `Choice` | Detects an injection in a prompt and picks the sentences where it starts and ends |
| `jev_linter_files` | `Noul` + 2 × `Choice` per smell | Checks each function and class for smells a linter can't judge |
| `jev_linter_project` | `Noul` per question | Checks pairs of related functions across files for design smells |
| `jev_linter_complete` | All of the above | Runs ruff, `jev_linter_files`, and `jev_linter_project` in order |

### guessing_game

The guessing game asks Jev to compare two integers. Plain code could do that, so the workflow works as a probe. It checks whether Jev gets trivial logic right and gives the same answer every time. The game also tests whether "pick at random" over 100 options gives a spread of picks or keeps landing on the same few numbers.

### prompt_injection_detection

This workflow splits the prompt into numbered sentences. It then asks three questions in a single request:

- `has_injection` asks whether the prompt contains an injection (`Noul`).
- `start` asks which sentence the injection starts at (`Choice`).
- `end` asks which sentence it ends at (`Choice`).

The workflow asks for `start` and `end` up front, before it knows whether an injection exists, and uses them only when `has_injection` ≥ 0.5. The speculative request saves a second round trip. When the span is valid, the workflow prints the injection and the prompt with the injection removed.

## jev_linter

The linter is a chain of three filters, ordered from cheapest to most nuanced. A file that passes one filter moves on to the next. A file that fails stops there, and its findings go into the report.

| Filter | Workflow | Checks |
| --- | --- | --- |
| `ruff_filter` | none (runs inside `jev_linter_complete`) | Ruff's rules, configured in `pyproject.toml` |
| `jev_linter_files` | `jev_linter_files` | Smells inside one function or class |
| `jev_linter_project` | `jev_linter_project` | Smells between functions, including across files |

Each workflow runs only its own filter. The operator makes sure the input meets that filter's contract. `jev_linter_files` expects files that pass ruff, and `jev_linter_project` expects files that pass `jev_linter_files`. `jev_linter_complete` runs all three in order and enforces those contracts itself.

Every workflow asks for a file or directory, with the project root as the default. Ruff decides which Python files count as part of the project, so `.venv`, git-ignored files, and `input_files/` are skipped.

### ruff_filter

Ruff's rule set lives only in `pyproject.toml`, so the editor, the command line, and the pipeline all enforce the same rules. On top of ruff's defaults, the config enables `B` (bugbear), `C90` (complexity), `ERA` (commented-out code), `FBT` (boolean traps), `PLR` (pylint refactor rules), and `S` (bandit security). `ANN` (type annotations) is left out for now, because most of the existing code is unannotated.

### jev_linter_files

The workflow extracts every function, method, and class with `ast` and sends one Jev request per unit. The state holds the unit's code and the source of any module-level constants it reads. Each smell gets three questions:

- A `Noul` asks whether the unit has the smell.
- Two speculative `Choice`s ask which line the clearest instance starts and ends on.

The options are the unit's numbered lines, so a finding points at specific lines. Classes, and units with more than 255 non-blank lines, are reported whole.

| Applies to | Smells |
| --- | --- |
| Functions and methods | Poor naming, Side effects in unexpected places, Excessive comments, Magic numbers, Primitive obsession, Law of Demeter |
| Classes | God class |

### jev_linter_project

The workflow first builds a graph of the given files in plain code. Only those files enter the graph, so a call into a file outside the list is never checked. The graph holds three kinds of candidates:

- **Knowledge pairs** are functions that share distinctive string tokens or have overlapping signatures. String tokens include the module constants a function reads, so a regex in a constant still counts.
- **Call edges** are caller and callee pairs that static analysis can resolve, through imports, `self` methods, constructors, and parameters annotated with a project class.
- **Constructions** are places where a function builds a project class or a third-party class itself. Dataclasses and standard-library classes are skipped.

Each candidate gets one Jev request. The state includes each unit's code, module constants, and contract, which code extracts from parameters, return type, side-effect calls, docstring, `assert`s, and `raise`s.

| Smell | Asked about | How it's decided |
| --- | --- | --- |
| Duplicated knowledge | Knowledge pairs | `Noul`, plus the span in each function |
| Drift | Knowledge pairs | Speculative `Noul`, used only when the pair is duplicated |
| Shotgun surgery | Computed in code | Groups of 3 or more functions joined by duplicated knowledge |
| Feature envy | Call edges into another class's method | `Noul` |
| Redundant validation | Call edges | `Noul` |
| Missing validation | Call edges | P(outside data crosses the call) × (1 − P(it's checked)) |
| Missing dependency injection | Constructions | `Noul` |

A finding that involves two functions fails both files, and the report lists the other side under `related`.

### Findings

Each linter workflow prints a text report and saves `outputs/<run_name>_findings.json`. The JSON is meant for a refactoring agent to consume.

```json
{
  "passed_all": ["main.py"],
  "filters": [
    {
      "source": "jev_linter_project",
      "checked": ["..."],
      "passed": ["..."],
      "notes": ["137 units, 46 knowledge pairs, 111 call edges, 17 constructions"],
      "findings": [
        {
          "file": "logged_jev.py",
          "start_line": 32,
          "end_line": 33,
          "rule": "Duplicated knowledge",
          "source": "jev_linter_project",
          "message": "`LoggedJev.system_one` and `parse_log`: both encode the same knowledge, so changing it means editing both",
          "probability": 0.64,
          "related": [{"file": "scripts/evaluate_determinism.py", "start_line": 60, "end_line": 66}]
        }
      ]
    }
  ]
}
```

Jev findings are recorded at a probability of 0.5 or higher. Ruff findings have a `probability` of `null`. `passed_all` lists the files that cleared every filter in the run.

Each filter also records its `usage`, and the report has a `total_usage`. Both count requests, input tokens, and output tokens, and give an estimated cost.

### Progress and cost

While a filter runs, the workflow rewrites one line in place with the current step, such as `jev_linter_files  [ 37/152]  logged_jev.py  LoggedJev.system_one`. When the filter finishes, it prints how many files passed. Filters never print themselves. They report to a `Progress` object, and only the workflows pass in `ConsoleProgress`, so scripts get silent filters by default.

The text report ends with a cost table:

```
Cost (estimated from input tokens)
  filter              requests  input tokens  output tokens  est. cost
  ruff_filter                0             0              0    $0.0000
  jev_linter_files         152       458,803        130,451    $0.0193
  jev_linter_project        16        17,301          2,697    $0.0007
  total                    168       476,104        133,148    $0.0200
```

The estimate uses TypeSafe's published rate of $42 per billion input tokens, and output tokens are free. The rate lives in `DOLLARS_PER_INPUT_TOKEN` in `jev_linter/report.py`, so update it there if pricing changes.

### Known limitations

- Missing validation is noisy. Jev counts file paths and command-line arguments as outside data, so it fires on most edges that carry a path.
- Drift scores high on nearly every duplicated pair, even when the copies currently agree.
- Static analysis can't see calls made through dynamic dispatch, such as `module.start_workflow` in `workflow_repl.py`.
- The project graph treats the working directory as the project root, so run the linter from the root.

## Adding a workflow

Drop a `.py` file into `workflows/`. The menu picks up any module that defines `start_workflow`.

```python
from run_context import RunContext


def start_workflow(context: RunContext) -> None:
    """Run interactively. Called by the menu."""


def repeatable_request(context: RunContext, input_path):
    """Send one non-interactive request. Used by scripts/repeat_workflow.py."""
```

- `context.jev` satisfies the `JevClient` protocol in `jev_client.py`. Call `context.jev.system_one(state, questions)` exactly as you would on `TypeSafeClient`, and the call gets logged.
- `context.save(suffix, content)` writes `<run_name>_<suffix>` next to the run's log and returns its path.
- `repeatable_request` is optional, and only the repeat script needs it. It receives a path relative to the project root, or `None` when no path is given.
- Put example inputs in `input_files/<workflow>/`.

`run_context.start_run` is the only code that builds a run name, and `workflow_name_of` is the only code that parses one.

The menu imports every module in `workflows/` when it scans them, so keep module-level code free of side effects.

## Measuring determinism

The repeat script sends one workflow's request N times and logs the calls to `outputs/scripts/`:

```sh
python scripts/repeat_workflow.py jev_linter_files input_files/code_smell_detector/order_processor.py -n 20
python scripts/repeat_workflow.py guessing_game -n 20
```

The evaluation script reads every log under `outputs/`. It groups calls whose workflow, model, state, and questions all match, then rebuilds `graphs/`:

```sh
python scripts/evaluate_determinism.py [--min-samples 2]
```

The script writes one folder per group, at `graphs/<workflow>/<label>_<model>/`. The label is the input's file stem, followed by the unit name when the state has one, such as `raw_logger.RawLogger.log`. Requests without a top-level filename, including `jev_linter_project`'s pair and edge requests, get a hash of the request instead. Each folder holds two kinds of output:

- `stats.csv` holds the mean, std, min, and max of each answer, plus how often each option was the top pick.
- `<question>.png` charts one question. A `Noul` chart counts runs at each returned P(yes). A `Choice` chart shows each option's mean probability with std error bars.

Interactive runs from `main.py` count too, so any request repeated by hand also shows up in the graphs.

`evaluate_determinism.py` deletes `graphs/` before rebuilding it. Raw logs in `outputs/` are not committed, so running the script on a fresh clone replaces the committed graphs with whatever your local logs support.

## Project layout

```
main.py                  Loads .env and starts the menu
workflow_repl.py         Finds workflows and runs the menu loop
run_context.py           RunContext, start_run, and run-name parsing
jev_client.py            JevClient protocol that workflows call
logged_jev.py            TypeSafeClient wrapper that logs each call
raw_logger.py            Owns the files under an output directory
pyproject.toml           Ruff configuration
jev_linter/              Filters, unit and graph extraction, and reports for the linter
workflows/               One module per workflow
input_files/<workflow>/  Example inputs
scripts/                 Repeat and determinism tools
graphs/                  Committed determinism results
outputs/                 Raw call logs and findings (git-ignored)
jev-skill.md             TypeSafe skill file used as agent context while building
```
