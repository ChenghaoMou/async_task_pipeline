import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
import queue
import time
from typing import Any

from async_task_pipeline.base.sentinel import EndSentinel
from async_task_pipeline.base.sentinel import FlushSentinel

from ..utils import logger
from .item import Message
from .item import PipelineItem
from .stage import PipelineStage


class AsyncTaskPipeline:
    """Main pipeline orchestrator with async I/O and thread-based processing"""

    def __init__(self, max_queue_size: int = 100, enable_timing: bool = True):
        self.max_queue_size = max_queue_size
        self.stages: list[PipelineStage] = []
        self.queues: list[queue.Queue[Message]] = []
        self.input_queue: queue.Queue[Message] | None = None
        self.output_queue: queue.Queue[Message] | None = None
        self.running = False
        self.sequence_counter = 0
        self.output_buffer: dict[int, PipelineItem] = {}
        self.next_output_seq = 0
        self.completed_items: list[PipelineItem] = []
        self.enable_timing = enable_timing

    def add_stage(self, name: str, process_fn: Callable) -> None:
        """Add a processing stage to the pipeline"""
        if not self.queues:
            self.input_queue = queue.Queue(maxsize=self.max_queue_size)
            input_q = self.input_queue
        else:
            input_q = self.queues[-1]

        output_q: queue.Queue[Message] = queue.Queue(maxsize=self.max_queue_size)
        self.queues.append(output_q)
        self.output_queue = output_q
        stage = PipelineStage(name, process_fn, input_q, output_q, enable_timing=self.enable_timing)
        self.stages.append(stage)

    async def start(self) -> None:
        """Start all pipeline stages"""
        self.running = True
        for stage in self.stages:
            stage.start()
        logger.info("Pipeline started")

    async def stop(self) -> None:
        """Stop all pipeline stages"""
        self.running = False
        for stage in reversed(self.stages):
            stage.stop()
        logger.info("Pipeline stopped")

    async def process_input_stream(self, input_stream: AsyncIterator[Any]) -> None:
        """Consume async input stream and feed to pipeline"""
        try:
            async for data in input_stream:
                await self.process_input_data(data, time.perf_counter())
        except Exception as e:
            logger.error(f"Error processing input stream: {e}")
        finally:
            await self.end_input_stream()

    async def end_input_stream(self) -> None:
        """End the input stream"""
        if not self.running:
            return
        logger.info("Ending input stream")
        if self.input_queue is not None:
            await asyncio.get_event_loop().run_in_executor(None, self.input_queue.put, EndSentinel())

    async def interrupt(self) -> None:
        """Interrupt the pipeline"""
        if not self.running:
            return
        self.clear()

    async def process_input_data(self, data: Any, created_at: float) -> None:
        try:
            if not self.running:
                return

            item = PipelineItem(
                seq_num=self.sequence_counter,
                data=data,
                enable_timing=self.enable_timing,
                start_timestamp=created_at,
            )
            self.sequence_counter += 1
            logger.debug(f"Input delay: {(time.perf_counter() - created_at) * 1000:.3f}ms")

            if self.input_queue is not None:
                await asyncio.get_event_loop().run_in_executor(None, self.input_queue.put, item)
                logger.debug(f"Queued input item {item.seq_num}")

        except Exception as e:
            logger.error(f"Error processing input stream: {e}")

    async def generate_output_stream(self) -> AsyncIterator[Any]:
        """Generate async output stream from pipeline, maintaining order"""
        while self.running or (self.output_queue and not self.output_queue.empty()) or self.output_buffer:
            try:
                item = await asyncio.get_event_loop().run_in_executor(None, self._get_output_nowait)

                match item:
                    case FlushSentinel():
                        continue
                    case EndSentinel():
                        break

                if item is not None:
                    self.output_buffer[item.seq_num] = item

                while self.next_output_seq in self.output_buffer:
                    ordered_item = self.output_buffer.pop(self.next_output_seq)

                    self.completed_items.append(ordered_item)

                    if self.enable_timing:
                        total_latency = ordered_item.get_total_latency()
                        stage_latencies = ordered_item.get_stage_latencies()
                        if stage_latencies is not None:
                            logger.info(f"Item {ordered_item.seq_num} completed - Total latency: {total_latency:.3f}s")
                            for stage, latency in stage_latencies.items():
                                logger.debug(f"  {stage}: {latency:.3f}s")

                    yield ordered_item.data
                    self.next_output_seq += 1

                if item is None:
                    await asyncio.sleep(0.001)

            except Exception as e:
                logger.error(f"Error generating output: {e}")
                await asyncio.sleep(0.001)

    def _get_output_nowait(self) -> Message | None:
        """Helper to get output without blocking"""
        try:
            if self.output_queue is not None:
                return self.output_queue.get_nowait()
            return None
        except queue.Empty:
            return None

    def get_latency_summary(self) -> dict[str, Any]:
        """Get summary statistics for pipeline latency"""
        if not self.completed_items:
            return {}

        total_latencies = [
            latency for item in self.completed_items if (latency := item.get_total_latency()) is not None
        ]
        avg_latency = sum(total_latencies) / len(total_latencies) if total_latencies else 0.0
        min_latency = min(total_latencies) if total_latencies else 0.0
        max_latency = max(total_latencies) if total_latencies else 0.0

        stage_stats = {}

        total_computation_ratios = []

        for stage in self.stages:
            stage_latencies = []
            stage_computation_times = []
            stage_queue_wait_times = []
            stage_transmission_times = []

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

                stage_stats[stage.name] = {
                    "avg_latency": sum(stage_latencies) / len(stage_latencies),
                    "min_latency": min(stage_latencies),
                    "max_latency": max(stage_latencies),
                    "processed_count": stage.processed_count,
                    "avg_processing_time": stage.get_average_processing_time(),
                    "timing_breakdown": {
                        "avg_computation_time": avg_computation,
                        "avg_queue_wait_time": avg_queue_wait,
                        "avg_transmission_time": avg_transmission,
                        "computation_ratio": avg_computation / (avg_computation + avg_queue_wait + avg_transmission)
                        if (avg_computation + avg_queue_wait + avg_transmission) > 0
                        else 0.0,
                    },
                }

        for item in self.completed_items:
            if (breakdown := item.get_timing_breakdown()) is not None and "totals" in breakdown:
                total_computation_ratios.append(breakdown["totals"]["computation_ratio"])

        avg_computation_ratio = (
            sum(total_computation_ratios) / len(total_computation_ratios) if total_computation_ratios else 0.0
        )

        return {
            "total_items": len(self.completed_items),
            "avg_total_latency": avg_latency,
            "min_total_latency": min_latency,
            "max_total_latency": max_latency,
            "stage_statistics": stage_stats,
            "overall_efficiency": {
                "computation_efficiency": avg_computation_ratio,
                "overhead_ratio": 1.0 - avg_computation_ratio,
            },
        }

    def clear(self) -> None:
        """Clear the pipeline"""
        self.clear_input_queue()
        self.clear_output_queue()

        for stage in self.stages:
            stage.clear_input_queue()

        self.completed_items = []
        self.output_buffer = {}
        self.next_output_seq = 0
        self.sequence_counter = 0

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
