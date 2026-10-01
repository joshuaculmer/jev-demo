from pathlib import Path


class RawLogger:
    """Owns the files under one output directory."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def log_path(self, run_name):
        return self.directory / f"{run_name}.txt"

    def log(self, run_name, raw_text):
        """Append raw text to the run's log."""

        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.log_path(run_name), "a", encoding="utf-8") as file:
            file.write(raw_text + "\n\n")

    def save(self, filename, content):
        """Write content to <directory>/<filename>, replacing any earlier file."""

        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / filename
        path.write_text(content, encoding="utf-8")
        return path
