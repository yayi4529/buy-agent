from contextlib import AbstractAsyncContextManager
from typing import Protocol


class LockManager(Protocol):
    def lock(self, key: str) -> AbstractAsyncContextManager[None]: ...
