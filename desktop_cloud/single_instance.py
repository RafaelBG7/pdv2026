from __future__ import annotations

import os
from pathlib import Path

from .config import program_data_dir


class SingleInstanceLock:
    def __init__(self, name: str = "girofy-desktop.lock") -> None:
        self.path = program_data_dir() / "locks" / name
        self._handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            return self._acquire_windows()
        return self._acquire_posix()

    def release(self) -> None:
        if self._handle:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None

    def _open_handle(self):
        return self.path.open("a+", encoding="utf-8")

    def _acquire_windows(self) -> bool:
        import msvcrt

        self._handle = self._open_handle()
        try:
            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(str(os.getpid()))
            self._handle.flush()
            return True
        except OSError:
            self._handle.close()
            self._handle = None
            return False

    def _acquire_posix(self) -> bool:
        import fcntl

        self._handle = self._open_handle()
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(str(os.getpid()))
            self._handle.flush()
            return True
        except OSError:
            self._handle.close()
            self._handle = None
            return False

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("O Girofy já está aberto neste computador.")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()
