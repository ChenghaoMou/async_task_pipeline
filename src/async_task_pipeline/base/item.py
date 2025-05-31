from collections.abc import Callable
import functools
import time
from typing import Any
from typing import TypeVar
from typing import cast

from pydantic import BaseModel
from pydantic import Field

from async_task_pipeline.base.sentinel import EndSentinel
from async_task_pipeline.base.sentinel import FlushSentinel

from ..utils.metrics import DetailedTiming

T = TypeVar("T")


def _wrapper(func: Callable[..., T]) -> Callable[..., T | None]:
    """Wrapper a function to return None if timing is disabled"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T | None:
        if not args:
            return None
        _self = cast("PipelineItem", args[0])
        if _self.enable_timing:
            return func(*args, **kwargs)
        return None

    return wrapper


class PipelineItem(BaseModel):
    """
    Container for data flowing through pipeline with sequence and optional timing tracking.

    Parameters
    ----------
    seq_num : int
        Sequence number of the item in the pipeline.
    data : Any
        Data flowing through the pipeline.
    start_timestamp : float | None, optional
        Timestamp when the item entered the pipeline. Defaults to None.
    enable_timing : bool, optional
        Whether to enable timing tracking. Defaults to True.
    """

    seq_num: int
    data: Any
    enable_timing: bool = True
    start_timestamp: float = Field(default_factory=time.perf_counter)
    _stage_timestamps: dict[str, float]
    _detailed_timings: dict[str, DetailedTiming]
    _queue_enter_times: dict[str, float]

    def model_post_init(self, __context: Any) -> None:
        """Initialize the item"""
        self._stage_timestamps = {}
        self._detailed_timings = {}
        self._queue_enter_times = {}

    @_wrapper
    def record_queue_entry(self, stage_name: str) -> None:
        """Record when item enters a stage's input queue"""
        self._queue_enter_times[stage_name] = time.perf_counter()

    @_wrapper
    def record_stage_completion(self, stage_name: str) -> None:
        """Record when a stage completes processing this item"""
        self._stage_timestamps[stage_name] = time.perf_counter()

    @_wrapper
    def record_detailed_timing(self, stage_name: str, detailed_timing: DetailedTiming) -> None:
        """Record detailed timing for a stage"""
        self._detailed_timings[stage_name] = detailed_timing

    @_wrapper
    def get_queue_enter_time(self, stage_name: str) -> float | None:
        """Get the time the item entered the queue for a stage"""
        if stage_name not in self._queue_enter_times:
            return None
        return self._queue_enter_times[stage_name]

    @_wrapper
    def get_stage_completion_time(self, stage_name: str) -> float | None:
        """Get the time the item completed processing for a stage"""
        if stage_name not in self._stage_timestamps:
            return None
        return self._stage_timestamps[stage_name]

    @_wrapper
    def get_detailed_timing(self, stage_name: str) -> DetailedTiming | None:
        """Get the detailed timing for a stage"""
        if stage_name not in self._detailed_timings:
            return None
        return self._detailed_timings[stage_name]

    @_wrapper
    def get_total_latency(self) -> float | None:
        """Calculate total end-to-end latency"""
        if not self._stage_timestamps or self.start_timestamp is None:
            return None

        last_timestamp = max(self._stage_timestamps.values())
        return last_timestamp - self.start_timestamp

    @_wrapper
    def get_stage_latencies(self) -> dict[str, float] | None:
        """Calculate latency for each stage"""
        if not self._stage_timestamps or self.start_timestamp is None:
            return None
        latencies = {}
        sorted_stages = sorted(self._stage_timestamps.items(), key=lambda x: x[1])

        prev_time = self.start_timestamp
        for stage_name, timestamp in sorted_stages:
            latencies[stage_name] = timestamp - prev_time
            prev_time = timestamp

        return latencies

    @_wrapper
    def get_timing_breakdown(self) -> dict[str, dict[str, float]] | None:
        """Get detailed timing breakdown for each stage"""
        if not self._detailed_timings or self.start_timestamp is None:
            return None

        breakdown: dict[str, dict[str, float]] = {}
        for stage_name, timing in self._detailed_timings.items():
            breakdown[stage_name] = {
                "queue_wait_time": timing.queue_wait_time,
                "computation_time": timing.computation_time,
                "transmission_time": timing.transmission_time,
                "total_stage_time": timing.queue_wait_time + timing.computation_time + timing.transmission_time,
            }

        total_latency = self.get_total_latency()
        events: list[tuple[float, str, str | None]] = [(self.start_timestamp, "start", None)]

        for stage_name, timing in self._detailed_timings.items():
            events.append((timing.processing_start_time, "compute_start", stage_name))
            events.append((timing.processing_end_time, "compute_end", stage_name))

        events.sort(key=lambda x: x[0])

        total_computation_time = 0.0
        last_time = self.start_timestamp
        computing_stages: set[str | None] = set()

        for event_time, event_type, _stage_name in events:
            if computing_stages:
                total_computation_time += event_time - last_time

            if event_type == "compute_start":
                computing_stages.add(_stage_name)
            elif event_type == "compute_end":
                computing_stages.discard(_stage_name)

            last_time = event_time

        end_time = self.start_timestamp + total_latency if total_latency else 0.0
        if computing_stages and last_time < end_time:
            total_computation_time += end_time - last_time

        total_overhead_time = total_latency - total_computation_time if total_latency else 0.0

        if breakdown:
            breakdown["totals"] = {
                "total_computation_time": total_computation_time,
                "total_overhead_time": total_overhead_time,
                "total_latency": total_latency if total_latency is not None else 0.0,
                "computation_ratio": (total_computation_time / total_latency) if total_latency else 0.0,
            }

        return breakdown


type Message = PipelineItem | FlushSentinel | EndSentinel
