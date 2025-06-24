from collections.abc import Callable
import functools
import time
from typing import Any
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import Field
from pydantic import PrivateAttr

from async_task_pipeline.utils.metrics import DetailedTiming

T = TypeVar("T")
DataT = TypeVar("DataT")


def _if_timing_enabled(func: Callable[..., T]) -> Callable[..., T | None]:
    """Wrapper a function to return None if timing is disabled"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T | None:
        if not args:
            return func(*args, **kwargs)
        if not isinstance(args[0], PipelineItem):
            return func(*args, **kwargs)
        _self = args[0]
        return func(*args, **kwargs) if _self.enable_timing else None

    return wrapper


class PipelineItem(BaseModel, Generic[DataT]):
    """Data container for pipeline processing.

    A wrapper class that carries data through the pipeline along with metadata
    for tracking timing and performance analysis. Each item maintains
    detailed timing information as it flows through different pipeline stages.

    Parameters
    ----------
    data : DataT
        The actual data payload being processed through the pipeline.
    enable_timing : bool, default=True
        Whether to collect detailed timing information for performance analysis.
    start_timestamp : float, optional
        Timestamp when the item entered the pipeline. Auto-generated if not provided.
    """

    data: DataT
    enable_timing: bool = True
    start_timestamp: float = Field(default_factory=time.perf_counter)
    _completion_timestamps: dict[str, float] = PrivateAttr(default_factory=dict)
    _detailed_timings: dict[str, DetailedTiming] = PrivateAttr(default_factory=dict)
    _entry_timestamps: dict[str, float] = PrivateAttr(default_factory=dict)

    @_if_timing_enabled
    def record_entry_time(self, stage_name: str) -> None:
        """Record when item enters a stage's input queue.

        Parameters
        ----------
        stage_name : str
            Name of the stage whose queue the item is entering.
        """
        self._entry_timestamps[stage_name] = time.perf_counter()

    @_if_timing_enabled
    def record_completion_time(self, stage_name: str) -> None:
        """Record when a stage completes processing this item.

        Parameters
        ----------
        stage_name : str
            Name of the stage that completed processing.
        """
        self._completion_timestamps[stage_name] = time.perf_counter()

    @_if_timing_enabled
    def record_detailed_timing(self, stage_name: str, detailed_timing: DetailedTiming) -> None:
        """Record detailed timing for a stage"""
        self._detailed_timings[stage_name] = detailed_timing

    @_if_timing_enabled
    def get_entry_time(self, stage_name: str) -> float | None:
        """Get the time the item entered the queue for a stage"""
        if stage_name not in self._entry_timestamps:
            return None
        return self._entry_timestamps[stage_name]

    @_if_timing_enabled
    def get_completion_time(self, stage_name: str) -> float | None:
        """Get the time the item completed processing for a stage"""
        if stage_name not in self._completion_timestamps:
            return None
        return self._completion_timestamps[stage_name]

    @_if_timing_enabled
    def get_detailed_timing(self, stage_name: str) -> DetailedTiming | None:
        """Get the detailed timing for a stage"""
        if stage_name not in self._detailed_timings:
            return None
        return self._detailed_timings[stage_name]

    @_if_timing_enabled
    def get_total_latency(self) -> float | None:
        """Calculate total end-to-end latency.

        Computes the time from when the item entered the pipeline until
        the last stage completed processing it.

        Returns
        -------
        float | None
            Total latency in seconds, or None if timing is disabled or
            no stages have completed processing.
        """
        if not self._completion_timestamps or self.start_timestamp is None:
            return None

        last_timestamp = max(self._completion_timestamps.values())
        return last_timestamp - self.start_timestamp

    @_if_timing_enabled
    def get_stage_latencies(self) -> dict[str, float] | None:
        """Calculate latency for each stage"""
        if not self._completion_timestamps or self.start_timestamp is None:
            return None
        latencies: dict[str, float] = {}
        sorted_stages = sorted(self._completion_timestamps.items(), key=lambda x: x[1])

        prev_time = self.start_timestamp
        for stage_name, timestamp in sorted_stages:
            latencies[stage_name] = timestamp - prev_time
            prev_time = timestamp

        return latencies

    @_if_timing_enabled
    def get_timing_breakdown(self) -> dict[str, dict[str, float]] | None:
        """Get detailed timing breakdown for each stage.

        Provides comprehensive timing analysis including queue wait times,
        computation times, transmission times, and overall efficiency metrics.

        Returns
        -------
        dict[str, dict[str, float]] | None
            Dictionary with per-stage timing breakdowns and totals, including:
            - Per-stage: queue_wait_time, computation_time, transmission_time
            - Totals: total_computation_time, total_overhead_time, computation_ratio
            Returns None if timing is disabled or no detailed timings available.
        """
        if not self._detailed_timings or self.start_timestamp is None:
            return None

        breakdown: dict[str, dict[str, float]] = {
            stage_name: {
                "queue_wait_time": timing.queue_wait_time,
                "computation_time": timing.computation_time,
                "transmission_time": timing.transmission_time,
                "total_stage_time": timing.queue_wait_time + timing.computation_time + timing.transmission_time,
            }
            for stage_name, timing in self._detailed_timings.items()
        }
        total_latency = self.get_total_latency()
        events: list[tuple[float, str, str | None]] = [(self.start_timestamp, "start", None)]

        for stage_name, timing in self._detailed_timings.items():
            events.extend(
                (
                    (timing.processing_start_time, "compute_start", stage_name),
                    (timing.processing_end_time, "compute_end", stage_name),
                )
            )
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

        end_time = self.start_timestamp + (total_latency or 0.0)
        if computing_stages and last_time < end_time:
            total_computation_time += end_time - last_time

        total_overhead_time = total_latency - total_computation_time if total_latency else 0.0

        breakdown["totals"] = {
            "total_computation_time": total_computation_time,
            "total_overhead_time": total_overhead_time,
            "total_latency": total_latency if total_latency is not None else 0.0,
            "computation_ratio": (total_computation_time / total_latency) if total_latency else 0.0,
        }

        return breakdown
