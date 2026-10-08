"""Run an export in a separate process (same CLI users run), stream its JSONL events, support cancel."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from ..job import Job


class ExportRunner(QObject):
    event = Signal(dict)  # {"event": "stage"|"warning"|"log"|"done"|"error", ...}
    finished = Signal(bool, list, str)  # ok, output paths, error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._buf = ""
        self._outputs: list[str] = []
        self._error = ""
        self._cancelled = False
        self._job_file: Path | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def start(self, job: Job, both: bool = False) -> None:
        if self.running:
            return
        fd, name = tempfile.mkstemp(prefix="md2doc_job_", suffix=".json")
        Path(name).write_text(job.model_dump_json(indent=1, exclude_defaults=True), encoding="utf-8")
        import os

        os.close(fd)
        self._job_file = Path(name)
        self._buf, self._outputs, self._error, self._cancelled = "", [], "", False
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        p.readyReadStandardOutput.connect(self._on_stdout)
        p.readyReadStandardError.connect(self._on_stderr)
        p.finished.connect(self._on_finished)
        p.errorOccurred.connect(self._on_error)
        export_args = ["export", "--job", name, "--jsonl"] + (["--both"] if both else [])
        if getattr(sys, "frozen", False):  # packaged app: the console CLI sits next to the GUI exe
            program, args = str(Path(sys.executable).with_name("md2doc.exe")), export_args
        else:  # -I: ignore cwd/env imports
            program, args = sys.executable, ["-I", "-m", "md2doc"] + export_args
        p.setWorkingDirectory(tempfile.gettempdir())
        env = p.processEnvironment()
        from PySide6.QtCore import QProcessEnvironment

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        p.setProcessEnvironment(env)
        self._proc = p
        p.start(program, args)

    def cancel(self) -> None:
        if not self.running:
            return
        self._cancelled = True
        pid = self._proc.processId()
        # QProcess.kill() would only terminate this one process and orphan node + msedge
        import os

        tk = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")  # absolute: never the cwd
        subprocess.run([tk, "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)

    # ------------------------------------------------------------------------------------------
    def _on_stdout(self) -> None:
        self._buf += bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("event") == "done":
                self._outputs.append(ev.get("output", ""))
            elif ev.get("event") == "error":
                self._error = ev.get("message", "export failed")
            self.event.emit(ev)

    def _on_stderr(self) -> None:
        text = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace").strip()
        if text:
            self.event.emit({"event": "log", "message": text})
            if not self._error and "Traceback" in text:
                self._error = text.splitlines()[-1]

    def _on_error(self, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._error = "Could not start the export process."

    def _on_finished(self, code: int, _status) -> None:
        self._on_stdout()
        if self._job_file:
            self._job_file.unlink(missing_ok=True)
        ok = code == 0 and bool(self._outputs) and not self._cancelled
        if self._cancelled:
            self._error = "Export cancelled."
        elif code not in (0, 2) and not self._error:
            self._error = f"The export process exited with code {code}."
        self.finished.emit(ok or (code == 2 and bool(self._outputs)), self._outputs, self._error)
