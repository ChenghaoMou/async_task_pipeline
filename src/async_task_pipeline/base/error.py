"""Pipeline-specific exception classes."""


class PipelineStatusError(Exception):
    """Exception raised when the pipeline is not in the expected status.

    This exception is raised when attempting operations that require the
    pipeline to be in a specific state (e.g., trying to process data when
    the pipeline is not running, or trying to start an already running pipeline).

    Parameters
    ----------
    message : str
        Descriptive error message explaining the status conflict.

    Attributes
    ----------
    message : str
        The error message provided during initialization.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)
