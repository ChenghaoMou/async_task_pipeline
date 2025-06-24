import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
import queue
import time
from typing import Any
from typing import Generic
from typing import TypeVar

from async_task_pipeline.base.models import EfficiencyMetrics
from async_task_pipeline.base.models import ItemTimingBreakdown
from async_task_pipeline.base.models import ItemTimingTotals
from async_task_pipeline.base.models import LatencySummary
from async_task_pipeline.base.models import PipelineAnalysis
from async_task_pipeline.base.models import StageStatistics
from async_task_pipeline.base.models import StageTimingDetail
from async_task_pipeline.base.models import TimingBreakdown

from ..utils import logger
from .item import PipelineItem
from .stage import PipelineStage

T = TypeVar("T")
U = TypeVar("U")


class AsyncTaskPipeline(Generic[T, U]):
    """Main pipeline orchestrator with async I/O and thread-based processing.

    This class manages a multi-stage data processing pipeline that combines
    async I/O for input/output operations with thread-based processing for
    CPU-intensive tasks. It provides comprehensive timing analysis and
    performance monitoring capabilities. It takes two type parameters:

    - T: The type of the data you want to process (e.g. messages, signals or events)
    - U: The type of the pass-through data (e.g. exceptions)

    Parameters
    ----------
    max_queue_size : int, default=100
        Maximum size for inter-stage queues. Controls memory usage and back pressure.
    enable_timing : bool, default=False
        Whether to enable detailed timing analysis for performance monitoring.
    return_exceptions : bool, default=False
        Whether to return exceptions in the output stream.

    Examples
    --------
    >>> pipeline = AsyncTaskPipeline(max_queue_size=50, enable_timing=True)
    >>> pipeline.add_stage("process", lambda x: x * 2)
    >>> await pipeline.start()
    """

    def __init__(self, max_queue_size: int = 100, enable_timing: bool = False, return_exceptions: bool = False):
        self.max_queue_size = max_queue_size
        self.enable_timing = enable_timing
        self.return_exceptions = return_exceptions

        self.stages: list[PipelineStage] = []
        self.queues: list[queue.Queue[PipelineItem[T] | U]] = []
        self.input_queue: queue.Queue[PipelineItem[T] | U] | None = None
        self.output_queue: queue.Queue[PipelineItem[T] | U] | None = None
        self.running = False
        self.counter = 0
        self.completed_items: list[PipelineItem[T]] = []
        self._sleep_time = 0.001

    def add_stage(self, name: str, process_fn: Callable) -> None:
        """Add a processing stage to the pipeline.

        Creates a new stage with the specified processing function and connects
        it to the pipeline's queue system. Stages are executed in the order
        they are added.

        Parameters
        ----------
        name : str
            Unique identifier for this stage, used in timing analysis and logging.
        process_fn : Callable
            Function to process data items. Should accept a single argument and
            return processed data, None (to filter), or a generator (to produce
            multiple outputs).

        Notes
        -----
        The process_fn should be thread-safe as it will be executed in a
        separate thread. If the function returns None, the item is filtered
        out. If it returns a generator, each yielded value becomes a separate
        pipeline item.
        """
        if not self.queues:
            self.input_queue = queue.Queue(maxsize=self.max_queue_size)
            input_q = self.input_queue
        else:
            input_q = self.queues[-1]

        output_q: queue.Queue[PipelineItem[T] | U] = queue.Queue(maxsize=self.max_queue_size)
        self.queues.append(output_q)
        self.output_queue = output_q
        stage = PipelineStage(
            name,
            process_fn,
            input_q,
            output_q,
            enable_timing=self.enable_timing,
            return_exceptions=self.return_exceptions,
        )
        self.stages.append(stage)

    async def start(self) -> None:
        """Start all pipeline stages.

        Initializes and starts worker threads for all registered stages.
        The pipeline must be started before processing any data.

        Raises
        ------
        RuntimeError
            If the pipeline is already running or if no stages have been added.
        """
        self.running = True
        for stage in self.stages:
            stage.start()
        logger.info("Pipeline started")

    async def stop(self) -> None:
        """Stop all pipeline stages.

        Gracefully shuts down all worker threads and clears pipeline state.
        This method should be called when pipeline processing is complete.

        Notes
        -----
        Stages are stopped in reverse order to ensure proper cleanup.
        Any remaining items in queues will be lost.
        """
        self.running = False
        for stage in reversed(self.stages):
            stage.stop()
        logger.info("Pipeline stopped")

    async def process_input_stream(self, input_stream: AsyncIterator[Any]) -> None:
        """Consume async input stream and feed to pipeline.

        Processes an async iterator/generator and feeds each item into the
        pipeline for processing. This method handles the async-to-sync
        bridge for pipeline input.

        Parameters
        ----------
        input_stream : AsyncIterator[Any]
            Async iterator that yields data items to be processed.

        Notes
        -----
        This method will consume the entire input stream. For continuous
        processing, use individual `process_input_data` calls.
        """
        try:
            async for data in input_stream:
                await self.process_input_data(data, time.perf_counter())
        except Exception as e:
            logger.error(f"Error processing input stream: {e}")
            raise

    async def interrupt(self) -> None:
        """Interrupt the pipeline"""
        if not self.running:
            return
        self.clear()

    async def process_input_data(self, data: T, created_at: float) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self.put_input_data, data, created_at)

    async def process_input_sentinel(self, sentinel: U) -> None:
        await asyncio.get_event_loop().run_in_executor(None, self.put_input_sentinel, sentinel)

    def put_input_sentinel(self, sentinel: U) -> None:
        """
        Put a sentinel value into the input queue.

        This method is used to signal the end of the input stream.
        It is typically used in conjunction with `process_input_stream`.

        Parameters
        ----------
        sentinel : U
            The sentinel value to put into the input queue.

        Raises
        ------
        RuntimeError
            If the pipeline is not running.
        """
        if not self.running:
            raise RuntimeError("Pipeline is not running")

        try:
            if self.input_queue is not None:
                self.input_queue.put(sentinel)
            else:
                raise RuntimeError("Input queue is not initialized")
        except Exception as e:
            logger.error(f"Error putting input sentinel: {e}")
            raise

    def put_input_data(self, data: T, created_at: float) -> None:
        """
        Put data into the input queue.

        This method is used to feed data into the pipeline.
        It is typically used in conjunction with `process_input_data`.

        Parameters
        ----------
        data : T
            The data to put into the input queue.
        created_at : float
            The timestamp when the data was created.

        Raises
        ------
        RuntimeError
            If the pipeline is not running.
        """
        if not self.running:
            raise RuntimeError("Pipeline is not running")

        try:
            item = PipelineItem[T](
                data=data,
                enable_timing=self.enable_timing,
                start_timestamp=created_at,
            )
            if self.input_queue is not None:
                self.input_queue.put(item)
                self.counter += 1
            else:
                raise RuntimeError("Input queue is not initialized")
        except Exception as e:
            logger.error(f"Error putting input data: {e}")
            raise

    async def generate_output_stream(self) -> AsyncIterator[T | U]:
        """Generate async output stream from pipeline, maintaining order.

        Creates an async iterator that yields processed items as they become
        available from the pipeline. Items are yielded in the order they
        were processed (which may differ from input order due to parallel
        processing).

        Yields
        ------
        T | U
            Processed data items or sentinel values from the pipeline.

        Notes
        -----
        This method will continue yielding items until the pipeline is stopped
        and all queues are empty. It's typically used in an async for loop.
        """
        while self.running or (self.output_queue and not self.output_queue.empty()):
            try:
                item = await asyncio.get_event_loop().run_in_executor(None, self._get_output_nowait)
                if item is None:
                    await asyncio.sleep(self._sleep_time)
                    continue

                if isinstance(item, PipelineItem):
                    yield item.data
                    if self.enable_timing:
                        self.completed_items.append(item)
                else:
                    yield item

            except Exception as e:
                logger.error(f"Error generating output: {e}")
                await asyncio.sleep(self._sleep_time)

    def _get_output_nowait(self) -> PipelineItem[T] | U | None:
        """Helper to get output without blocking"""
        try:
            return None if self.output_queue is None else self.output_queue.get_nowait()
        except queue.Empty:
            return None

    def get_report(self, include_item_details: bool = True) -> PipelineAnalysis | None:
        """Get summary statistics for pipeline latency.

        Computes comprehensive performance statistics including end-to-end
        latency, per-stage timing breakdowns, and efficiency metrics.

        Returns
        -------
        PipelineAnalysis | None
            Pipeline analysis including summary statistics and detailed item breakdowns.
            Returns None if no items have been processed or timing is disabled.

        Notes
        -----
        Only available when timing is enabled. Returns None if no
        items have been processed or timing is disabled.
        """
        if not self.completed_items:
            return None

        total_latencies = [
            latency for item in self.completed_items if (latency := item.get_total_latency()) is not None
        ]
        avg_latency = sum(total_latencies) / len(total_latencies) if total_latencies else 0.0
        min_latency = min(total_latencies, default=0.0)
        max_latency = max(total_latencies, default=0.0)

        stage_stats: dict[str, StageStatistics] = {}

        total_computation_ratios = []

        for stage in self.stages:
            stage_latencies: list[float] = []
            stage_computation_times: list[float] = []
            stage_queue_wait_times: list[float] = []
            stage_transmission_times: list[float] = []

            for item in self.completed_items:
                stage_latencies_dict = item.get_stage_latencies()
                if stage_latencies_dict is not None and stage.name in stage_latencies_dict:
                    stage_latencies.append(stage_latencies_dict[stage.name])

                if (timing := item.get_detailed_timing(stage.name)) is not None:
                    stage_computation_times.append(max(timing.computation_time, 0.0))
                    stage_queue_wait_times.append(max(timing.queue_wait_time, 0.0))
                    stage_transmission_times.append(max(timing.transmission_time, 0.0))

            if stage_latencies:
                avg_computation = (
                    sum(stage_computation_times) / len(stage_computation_times) if stage_computation_times else 0.0
                )
                avg_queue_wait = (
                    sum(stage_queue_wait_times) / len(stage_queue_wait_times) if stage_queue_wait_times else 0.0
                )
                avg_transmission = (
                    sum(stage_transmission_times) / len(stage_transmission_times) if stage_transmission_times else 0.0
                )

                stage_stats[stage.name] = StageStatistics(
                    avg_latency=sum(stage_latencies) / len(stage_latencies),
                    min_latency=min(stage_latencies),
                    max_latency=max(stage_latencies),
                    processed_count=stage.processed_count,
                    avg_processing_time=stage.get_average_processing_time(),
                    timing_breakdown=TimingBreakdown(
                        avg_computation_time=avg_computation,
                        avg_queue_wait_time=avg_queue_wait,
                        avg_transmission_time=avg_transmission,
                        computation_ratio=avg_computation / (avg_computation + avg_queue_wait + avg_transmission)
                        if (avg_computation + avg_queue_wait + avg_transmission) > 0
                        else 0.0,
                    ),
                )

        item_breakdowns: list[ItemTimingBreakdown] = []
        for item in self.completed_items:
            if (breakdown := item.get_timing_breakdown()) is not None and "totals" in breakdown:
                total_computation_ratios.append(breakdown["totals"]["computation_ratio"])
                if include_item_details:
                    item_breakdowns.append(
                        ItemTimingBreakdown(
                            totals=ItemTimingTotals(
                                total_computation_time=breakdown["totals"]["total_computation_time"],
                                total_overhead_time=breakdown["totals"]["total_overhead_time"],
                                total_latency=breakdown["totals"]["total_latency"],
                                computation_ratio=breakdown["totals"]["computation_ratio"],
                            ),
                            stages={
                                stage_name: StageTimingDetail(
                                    queue_wait_time=stage_data["queue_wait_time"],
                                    computation_time=stage_data["computation_time"],
                                    transmission_time=stage_data["transmission_time"],
                                    total_stage_time=stage_data["total_stage_time"],
                                )
                                for stage_name, stage_data in breakdown.items()
                                if stage_name != "totals" and isinstance(stage_data, dict)
                            },
                        )
                    )

        avg_computation_ratio = (
            sum(total_computation_ratios) / len(total_computation_ratios) if total_computation_ratios else 0.0
        )

        return PipelineAnalysis(
            summary=LatencySummary(
                total_items=len(self.completed_items),
                avg_total_latency=avg_latency,
                min_total_latency=min_latency,
                max_total_latency=max_latency,
                stage_statistics=stage_stats,
                overall_efficiency=EfficiencyMetrics(
                    computation_efficiency=avg_computation_ratio,
                    overhead_ratio=1.0 - avg_computation_ratio,
                ),
            ),
            item_breakdowns=item_breakdowns,
            analysis_metadata={
                "analysis_timestamp": time.time(),
                "enable_timing": self.enable_timing,
                "total_stages": len(self.stages),
                "pipeline_running": self.running,
            },
        )

    def clear(self) -> None:
        """Clear the pipeline state and queues.

        Removes all items from input/output queues and stage queues,
        resets completed items list, and resets the sequence counter.
        This method is useful for resetting the pipeline between runs.

        Notes
        -----
        This method should only be called when the pipeline is stopped.
        Any items currently being processed may be lost.
        """
        self.clear_input_queue()
        self.clear_output_queue()

        for stage in self.stages:
            stage.clear_input_queue()

        self.completed_items = []
        self.counter = 0

    def clear_input_queue(self) -> None:
        """Clear the input queue"""
        if self.input_queue is not None:
            while not self.input_queue.empty():
                self.input_queue.get()

    def clear_output_queue(self) -> None:
        """Clear the output queue"""
        if self.output_queue is not None:
            while not self.output_queue.empty():
                self.output_queue.get()
