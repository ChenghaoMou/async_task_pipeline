import time
from typing import Any

import pytest

from async_task_pipeline.base.item import PipelineItem
from async_task_pipeline.base.item import _if_timing_enabled
from async_task_pipeline.utils.metrics import DetailedTiming


@pytest.fixture
def item() -> PipelineItem[int]:
    return PipelineItem[int](data=1, enable_timing=True)


class TestDecorator:
    def test_enabled(self) -> None:
        @_if_timing_enabled
        def func(*args: Any, **kwargs: Any) -> Any:
            return "test"

        assert func(PipelineItem[int](data=1, enable_timing=True)) == "test"

    def test_disabled(self) -> None:
        @_if_timing_enabled
        def func(*args: Any, **kwargs: Any) -> Any:
            return "test"

        assert func(PipelineItem[int](data=1, enable_timing=False)) is None

    def test_error(self) -> None:
        @_if_timing_enabled
        def func(*args: Any, **kwargs: Any) -> Any:
            return "test"

        assert func(1, 2, 3) == "test"

    def test_empty(self) -> None:
        @_if_timing_enabled
        def func(*args: Any, **kwargs: Any) -> Any:
            return "test"

        assert func() == "test"


class TestPipelineItem:
    def test_record_entry_time(self, item: PipelineItem[int]) -> None:
        item.record_entry_time("stage1")
        assert item.get_entry_time("stage1") is not None
        assert item.get_completion_time("stage1") is None

    def test_record_completion_time(self, item: PipelineItem[int]) -> None:
        item.record_completion_time("stage1")
        assert item.get_completion_time("stage1") is not None
        assert item.get_entry_time("stage1") is None

    def test_get_detailed_timing(self, item: PipelineItem[int]) -> None:
        item.record_detailed_timing(
            "stage1",
            DetailedTiming(
                queue_enter_time=1,
                processing_start_time=2,
                processing_end_time=3,
                queue_exit_time=4,
            ),
        )
        assert item.get_detailed_timing("stage1") is not None
        assert item.get_detailed_timing("stage2") is None

    def test_get_total_latency(self, item: PipelineItem[int]) -> None:
        item.record_completion_time("stage1")
        latency = item.get_total_latency()
        assert latency is not None
        assert latency > 0

    def test_get_stage_latencies(self, item: PipelineItem[int]) -> None:
        item.record_completion_time("stage1")
        latencies = item.get_stage_latencies()
        assert latencies is not None
        assert latencies["stage1"] > 0

    def test_get_stage_latencies_none(self, item: PipelineItem[int]) -> None:
        latencies = item.get_stage_latencies()
        assert latencies is None

    def test_get_total_latency_none(self, item: PipelineItem[int]) -> None:
        latency = item.get_total_latency()
        assert latency is None

    def test_get_timing_breakdown_none(self, item: PipelineItem[int]) -> None:
        breakdown = item.get_timing_breakdown()
        assert breakdown is None

    def test_get_timing_breakdown(self, item: PipelineItem[int]) -> None:
        item.record_entry_time("stage1")
        item.record_completion_time("stage1")
        entry_time = item.get_entry_time("stage1") or 0
        time.sleep(1)
        end_time = item.get_completion_time("stage1") or 0
        item.record_detailed_timing(
            "stage1",
            DetailedTiming(
                queue_enter_time=entry_time,
                processing_start_time=entry_time + 1e-10,
                processing_end_time=end_time,
                queue_exit_time=end_time + 1e-10,
            ),
        )
        breakdown = item.get_timing_breakdown()
        assert breakdown is not None
        assert breakdown["stage1"] is not None
        assert breakdown["stage1"]["queue_wait_time"] > 0
        assert breakdown["stage1"]["computation_time"] > 0
        assert breakdown["stage1"]["transmission_time"] > 0
        assert breakdown["stage1"]["total_stage_time"] > 0
        assert breakdown["totals"] is not None
        assert breakdown["totals"]["total_computation_time"] > 0
        assert breakdown["totals"]["total_overhead_time"] > 0
        assert breakdown["totals"]["total_latency"] > 0
        assert breakdown["totals"]["computation_ratio"] > 0
