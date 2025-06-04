class PipelineStatusError(Exception):
    """Exception raised when the pipeline is not in the expected status"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
