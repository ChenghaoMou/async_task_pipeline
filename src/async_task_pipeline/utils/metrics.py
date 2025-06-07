from pydantic import BaseModel


class DetailedTiming(BaseModel):
    """Detailed timing information for a pipeline stage.

    Captures precise timing measurements for different phases of item
    processing within a pipeline stage, enabling detailed performance
    analysis and bottleneck identification.

    Parameters
    ----------
    queue_enter_time : float
        Timestamp when the item entered the stage's input queue.
    processing_start_time : float
        Timestamp when the stage began processing the item.
    processing_end_time : float
        Timestamp when the stage finished processing the item.
    queue_exit_time : float
        Timestamp when the processed item was placed in the output queue.
    """

    queue_enter_time: float
    processing_start_time: float
    processing_end_time: float
    queue_exit_time: float

    @property
    def queue_wait_time(self) -> float:
        """Time spent waiting in input queue.

        Returns
        -------
        float
            Duration in seconds between queue entry and processing start.
        """
        return max(0, self.processing_start_time - self.queue_enter_time)

    @property
    def computation_time(self) -> float:
        """Time spent in actual computation.

        Returns
        -------
        float
            Duration in seconds of the actual processing function execution.
        """
        return max(0, self.processing_end_time - self.processing_start_time)

    @property
    def transmission_time(self) -> float:
        """Time spent in transmission to next stage.

        Returns
        -------
        float
            Duration in seconds between processing completion and output queue placement.
        """
        return max(0, self.queue_exit_time - self.processing_end_time)
