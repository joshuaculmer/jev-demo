from pathlib import Path


class RawLogger:
    """Appends raw text to <directory>/<run_name>.txt."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def log(self, run_name, raw_text):
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / f"{run_name}.txt", "a", encoding="utf-8") as file:
            file.write(raw_text + "\n\n")
