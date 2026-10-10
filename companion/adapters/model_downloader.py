"""Model downloader with streaming progress via Qt signals."""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal


class DownloadWorker(QThread):
    progress = Signal(int, int)  # bytes_downloaded, total_bytes
    finished = Signal(str)  # dest path on success
    error = Signal(str)  # error message

    def __init__(self, url: str, dest: Path, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest = dest
        self._cancelled = False

    def run(self):
        try:
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            resp = requests.get(self.url, stream=True, timeout=30)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(self.dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self._cancelled:
                        resp.close()
                        return
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress.emit(downloaded, total)

            self.finished.emit(str(self.dest))
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._cancelled = True


def download_model(
    url: str,
    dest: Path,
    progress_callback=None,
    finished_callback=None,
    error_callback=None,
) -> DownloadWorker:
    worker = DownloadWorker(url, dest)
    if progress_callback:
        worker.progress.connect(progress_callback)
    if finished_callback:
        worker.finished.connect(finished_callback)
    if error_callback:
        worker.error.connect(error_callback)
    worker.start()
    return worker


def quick_download(url: str, dest: Path) -> bool:
    """Blocking download for simple cases. Returns True on success."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception:
        return False
