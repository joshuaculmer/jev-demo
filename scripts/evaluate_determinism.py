"""Measure how much Jev's answers vary across identical requests.

Reads every log in outputs/ and outputs/scripts/, groups calls whose workflow,
resolved model, state, and questions all match, and rebuilds graphs/ from scratch:

    graphs/<workflow>/<label>_<model>/stats.csv
    graphs/<workflow>/<label>_<model>/<question_id>.png

stats.csv columns:
    question, type, option, samples, mean, std, min, max, top_count

    noul    one row; values are P(yes); top_count = runs with P(yes) >= 0.5
    choice  one row per option; values are that option's probability; top_count = runs it was the pick
    score   one "score" row for the expected score, then one row per level like a choice

Usage:
    python scripts/evaluate_determinism.py [--min-samples 2]
"""

import argparse
import csv
import hashlib
import json
import re
import shutil
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
GRAPHS = ROOT / "graphs"

HEADER = re.compile(r"^=== (Request|Response) (\d+)(?: \([^)]*\))? ===$", re.MULTILINE)
TIMESTAMP = re.compile(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")

THRESHOLD = 0.5
TOP_OPTIONS = 10

SERIES = "#2a78d6"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"


# Parsing


def parse_log(path):
    """Return (request, response) pairs from one RawLogger file."""

    parts = HEADER.split(path.read_text(encoding="utf-8"))
    requests, responses = {}, {}
    for kind, number, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        (requests if kind == "Request" else responses)[number] = json.loads(body)
    return [(requests[n], responses[n]) for n in requests if n in responses]


def collect_groups():
    """Group identical requests across every log file."""

    groups = defaultdict(list)
    for path in sorted(OUTPUTS.rglob("*.txt")):
        workflow = TIMESTAMP.sub("", path.stem)
        for request, response in parse_log(path):
            body = json.dumps({"state": request["state"], "questions": request["questions"]}, sort_keys=True)
            groups[(workflow, response["model"], body)].append(response["answers"])
    return groups


def group_labels(keys):
    """Label each group by its state's filename, or a hash when there is none or it collides."""

    def digest(body):
        return hashlib.sha256(body.encode()).hexdigest()[:8]

    labels = {}
    for key in keys:
        state = json.loads(key[2])["state"]
        filename = state.get("filename") if isinstance(state, dict) else None
        labels[key] = Path(filename).stem if filename else digest(key[2])

    counts = Counter((key[0], key[1], label) for key, label in labels.items())
    for key, label in labels.items():
        if counts[(key[0], key[1], label)] > 1:
            labels[key] = f"{label}_{digest(key[2])}"
    return labels


# Statistics


def describe(values):
    return {
        "samples": len(values),
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def distribution_rows(question, kind, runs, picks):
    """One row per option: its probability across runs and how often it was the pick."""

    counts = Counter(picks)
    return [
        {"question": question, "type": kind, "option": option, **describe([run[option] for run in runs]), "top_count": counts[option]}
        for option in runs[0]
    ]


def question_rows(question, answers):
    kind = answers[0]["type"]

    if kind == "noul":
        values = [a["noul"] for a in answers]
        yes = sum(v >= THRESHOLD for v in values)
        return kind, [{"question": question, "type": kind, "option": "yes", **describe(values), "top_count": yes}]

    runs = [a["probabilities"] for a in answers]
    picks = [a["choice"] for a in answers] if kind == "choice" else [max(r, key=r.get) for r in runs]
    rows = distribution_rows(question, kind, runs, picks)

    if kind == "score":
        score = {"question": question, "type": kind, "option": "score", **describe([a["score"] for a in answers]), "top_count": ""}
        rows.insert(0, score)
    return kind, rows


# Graphs


def style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    ax.set_title(f"{title}\n", color=INK, fontsize=12, loc="left", fontweight="bold")
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)


def value_count_chart(ax, values, xlabel):
    """Bar per distinct value, height = number of runs that returned it."""

    counts = Counter(round(v, 4) for v in values)
    xs = sorted(counts)
    low, high = max(0.0, xs[0] - 0.03), min(1.0, xs[-1] + 0.03)

    ax.bar(xs, [counts[x] for x in xs], width=(high - low) / 40, color=SERIES)
    ax.set_xlim(low, high)
    if low < THRESHOLD < high:
        ax.axvline(THRESHOLD, color=MUTED, linestyle="--", linewidth=1)
        ax.text(THRESHOLD, 1.0, " 0.5 threshold", transform=ax.get_xaxis_transform(), color=MUTED, fontsize=8, va="top")
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel("runs", color=MUTED)
    ax.yaxis.get_major_locator().set_params(integer=True)


def save_graph(path, question, kind, rows, answers):
    """Noul: runs per returned P(yes). Choice and score: mean probability per option or level."""

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    n = rows[0]["samples"]

    if kind == "noul":
        row = rows[0]
        subtitle = f"noul · {n} runs · P(yes) mean {row['mean']:.3f}, std {row['std']:.4f} · yes in {row['top_count']}/{n}"
        value_count_chart(ax, [a["noul"] for a in answers], "P(yes)")
    else:
        options = [r for r in rows if r["option"] != "score"]
        top = max(options, key=lambda r: r["top_count"])
        shown = sorted(options, key=lambda r: r["mean"], reverse=True)[:TOP_OPTIONS]
        note = f"top {TOP_OPTIONS} of {len(options)} options" if len(options) > TOP_OPTIONS else f"{len(options)} options"
        subtitle = f"{kind} · {n} runs · picked '{top['option']}' in {top['top_count']}/{n} · {note} · bars show std"

        labels = [r["option"] if len(r["option"]) <= 12 else r["option"][:11] + "…" for r in shown]
        ax.bar(labels, [r["mean"] for r in shown], width=0.6, color=SERIES,
               yerr=[r["std"] for r in shown], ecolor=MUTED, capsize=3, error_kw={"linewidth": 1})
        ax.set_xlabel("option", color=MUTED)
        ax.set_ylabel("mean probability", color=MUTED)

    style(ax, question, subtitle)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


# Output


def summary_line(question, kind, rows, width):
    n = rows[0]["samples"]
    if kind == "noul":
        r = rows[0]
        detail = f"P(yes) {r['mean']:.3f} ± {r['std']:.4f}  range {r['min']:.2f}-{r['max']:.2f}  yes {r['top_count']}/{n}"
    else:
        options = [r for r in rows if r["option"] != "score"]
        top = max(options, key=lambda r: r["top_count"])
        detail = f"picked '{top['option']}' {top['top_count']}/{n}  P('{top['option']}') {top['mean']:.3f} ± {top['std']:.4f}"
        if kind == "score":
            detail = f"score {rows[0]['mean']:.3f} ± {rows[0]['std']:.4f}  " + detail
    return f"  {question:<{width}}  {kind:<6}  {detail}"


def safe_name(text):
    return re.sub(r"[^\w-]+", "_", text).strip("_")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-samples", type=int, default=2, help="skip groups with fewer identical requests (default 2)")
    args = parser.parse_args()

    groups = {key: runs for key, runs in collect_groups().items() if len(runs) >= args.min_samples}
    labels = group_labels(groups)

    shutil.rmtree(GRAPHS, ignore_errors=True)
    if not groups:
        print(f"No request was repeated at least {args.min_samples} times in {OUTPUTS}.")
        return

    for key, runs in sorted(groups.items(), key=lambda item: (item[0][0], labels[item[0]])):
        workflow, model, _ = key
        folder = GRAPHS / workflow / f"{labels[key]}_{model}"
        folder.mkdir(parents=True)

        print(f"\n{workflow} / {labels[key]} ({model}), {len(runs)} runs")
        width = max(len(q) for q in runs[0])

        all_rows = []
        for question in runs[0]:
            answers = [run[question] for run in runs]
            kind, rows = question_rows(question, answers)

            print(summary_line(question, kind, rows, width))
            save_graph(folder / f"{safe_name(question)}.png", question, kind, rows, answers)
            all_rows.extend(rows)

        with open(folder / "stats.csv", "w", newline="", encoding="utf-8") as file:
            fields = ["question", "type", "option", "samples", "mean", "std", "min", "max", "top_count"]
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"\nGraphs and stats.csv written to {GRAPHS}")


if __name__ == "__main__":
    main()
