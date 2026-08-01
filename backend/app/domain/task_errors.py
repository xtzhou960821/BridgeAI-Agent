"""Stable errors for persistent task use cases."""


class TaskNotFoundError(LookupError):
    """Raised when a requested task or run does not exist."""


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused with different input."""


class TaskInputConflictError(ValueError):
    """Raised when legacy task input conflicts with a persisted task."""


class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured PostgreSQL task store cannot be used."""


class LangGraphCheckpointerNotReadyError(RuntimeError):
    """Raised after a business run exists but its Checkpointer is not ready."""

    def __init__(self, run_id: str, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id


class TaskExecutionError(RuntimeError):
    """Raised when an Agent execution fails after a run is persisted."""

    def __init__(self, run_id: str, message: str) -> None:
        super().__init__(message)
        self.run_id = run_id
