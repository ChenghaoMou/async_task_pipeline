from pydantic import BaseModel


class DetailedTiming(BaseModel):
    """Detailed timing information for a pipeline stage"""

    queue_enter_time: float
    processing_start_time: float
    processing_end_time: float
    queue_exit_time: float

    @property
    def queue_wait_time(self) -> float:
        """Time spent waiting in input queue"""
        return self.processing_start_time - self.queue_enter_time

    @property
    def computation_time(self) -> float:
        """Time spent in actual computation"""
        return self.processing_end_time - self.processing_start_time

    @property
    def transmission_time(self) -> float:
        """Time spent in transmission to next stage"""
        return self.queue_exit_time - self.processing_end_time
