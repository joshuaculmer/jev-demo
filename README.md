# jev-demo

A small harness for building and testing workflows on [TypeSafe](https://docs.typesafe.ai)'s Jev model.

Each workflow is a plain Python module. An interactive menu runs workflows one at a time. Every call to Jev gets logged, and two scripts repeat a request many times and chart how much the answers vary.

## Setup

Requires Python 3.13 (tested with `typesafe-sdk` 0.7.2).

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

The menu lists every workflow in `workflows/`. Pick one by number, or enter `q` to quit. `Ctrl+C` stops the current workflow and returns to the menu.

Each run appends the raw JSON of every request and response to `outputs/<workflow>_<timestamp>.txt`.

## Included workflows

| Workflow | Primitives | What it does |
| --- | --- | --- |
| `guessing_game` | `Choice` | Jev picks a number from 1 to 100 and grades each guess as higher, lower, or match |
| `code_smell_detector` | 20 × `Noul` | Scores a file from `input_files/code_smell_detector/` against 20 code smells in one request |
| `prompt_injection_detection` | `Noul` + 2 × `Choice` | Detects an injection in a prompt and picks the sentences where it starts and ends |

### guessing_game

The guessing game asks Jev to compare two integers. Plain code could do that, so the workflow works as a probe. It checks whether Jev gets trivial logic right and gives the same answer every time. The game also tests whether "pick at random" over 100 options gives a spread of picks or keeps landing on the same few numbers.

### code_smell_detector

The detector sends the file's name and contents as state and asks one `Noul` per smell. The smells and their definitions live in `CODE_SMELLS`. It prints every smell sorted by probability and marks anything at or above 0.5 as detected.

### prompt_injection_detection

This workflow splits the prompt into numbered sentences. It then asks three questions in a single request:

- `has_injection` asks whether the prompt contains an injection (`Noul`).
- `start` asks which sentence the injection starts at (`Choice`).
- `end` asks which sentence it ends at (`Choice`).

The workflow asks for `start` and `end` up front, before it knows whether an injection exists, and uses them only when `has_injection` ≥ 0.5. The speculative request saves a second round trip. When the span is valid, the workflow prints the injection and the prompt with the injection removed.

## Adding a workflow

Drop a `.py` file into `workflows/`. The menu picks up any module that defines `start_workflow`.

```python
def start_workflow(jev):
    """Run interactively. Called by the menu."""

def repeatable_request(jev, input_path):
    """Send one non-interactive request. Used by scripts/repeat_workflow.py."""
```

- `jev` is a `LoggedJev`. Call `jev.system_one(state, questions)` exactly as you would on `TypeSafeClient`, and the call gets logged.
- `repeatable_request` is optional, and only the repeat script needs it. It receives a path in `input_files/<workflow>/`, or `None` when no file is given.
- Put example inputs in `input_files/<workflow>/`.

The menu imports every module in `workflows/` when it scans them, so keep module-level code free of side effects.

## Measuring determinism

The repeat script sends one workflow's request N times and logs the calls to `outputs/scripts/`:

```sh
python scripts/repeat_workflow.py code_smell_detector order_processor.py -n 20
python scripts/repeat_workflow.py guessing_game -n 20
```

The evaluation script reads every log under `outputs/`. It groups calls whose workflow, model, state, and questions all match, then rebuilds `graphs/`:

```sh
python scripts/evaluate_determinism.py [--min-samples 2]
```

The script writes one folder per group, at `graphs/<workflow>/<label>_<model>/`. Each label is the input's filename, or a hash of the request when it has no filename. Each folder holds two kinds of output:

- `stats.csv` holds the mean, std, min, and max of each answer, plus how often each option was the top pick.
- `<question>.png` charts one question. A `Noul` chart counts runs at each returned P(yes). A `Choice` chart shows each option's mean probability with std error bars.

Interactive runs from `main.py` count too, so any request repeated by hand also shows up in the graphs.

`evaluate_determinism.py` deletes `graphs/` before rebuilding it. Raw logs in `outputs/` are not committed, so running the script on a fresh clone replaces the committed graphs with whatever your local logs support.

## Project layout

```
main.py                  Loads .env and starts the menu
workflow_repl.py         Finds workflows and runs the menu loop
logged_jev.py            TypeSafeClient wrapper that logs each call
raw_logger.py            Appends text to outputs/<run_name>.txt
workflows/               One module per workflow
input_files/<workflow>/  Example inputs
scripts/                 Repeat and determinism tools
graphs/                  Committed determinism results
outputs/                 Raw call logs (git-ignored)
jev-skill.md             TypeSafe skill file used as agent context while building
```
