from collections.abc import Callable
import queue
import threading
import time
import types

from ..utils import logger
from ..utils.metrics import DetailedTiming
from .item import PipelineItem


class PipelineStage:
    """Single stage in the CPU-intensive task pipeline"""

    def __init__(
        self,
        name: str,
        process_fn: Callable,
        input_queue: queue.Queue,
        output_queue: queue.Queue,
        enable_timing: bool = True,
    ):
        self.name = name
        self.process_fn = process_fn
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.thread: threading.Thread | None = None
        self.running = False
        self.processed_count = 0
        self.total_processing_time = 0.0
        self.enable_timing = enable_timing

    def start(self) -> None:
        """Start the worker thread for this stage"""
        self.running = True
        self.thread = threading.Thread(target=self._worker, name=f"Stage-{self.name}")
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started pipeline stage: {self.name}")

    def stop(self) -> None:
        """Stop the worker thread"""
        self.running = False
        self.input_queue.put(None)
        if self.thread:
            self.thread.join()
        logger.info(f"Stopped pipeline stage: {self.name}")

    def _worker(self) -> None:
        """Worker thread that processes items from input queue"""
        while self.running:
            try:
                item = self.input_queue.get(timeout=1.0)
                if not isinstance(item, PipelineItem):
                    self.output_queue.put(item)
                    continue

                item.enable_timing = self.enable_timing
                processing_start_time = time.perf_counter()
                item.record_queue_entry(self.name)
                result_data = self.process_fn(item.data)
                if result_data is None:
                    continue

                processing_end_time = time.perf_counter()
                if isinstance(result_data, types.GeneratorType):
                    for result in result_data:
                        item.data = result
                        item.record_stage_completion(self.name)
                        self.output_queue.put(item)
                else:
                    item.data = result_data
                    item.record_stage_completion(self.name)
                    self.output_queue.put(item)

                transmission_end = time.perf_counter()

                if self.enable_timing:
                    detailed_timing = DetailedTiming(
                        queue_enter_time=item.get_queue_enter_time(self.name),
                        processing_start_time=processing_start_time,
                        processing_end_time=processing_end_time,
                        queue_exit_time=transmission_end,
                    )
                    item.record_detailed_timing(self.name, detailed_timing)

                    process_time = processing_end_time - processing_start_time
                    self.total_processing_time += process_time

                    logger.debug(
                        f"{self.name} processed item {item.seq_num}: "
                        f"queue_wait={detailed_timing.queue_wait_time * 1000:.2f}ms, "
                        f"computation={detailed_timing.computation_time * 1000:.2f}ms, "
                        f"transmission={detailed_timing.transmission_time * 1000:.2f}ms"
                    )

                self.processed_count += 1

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in {self.name}: {e}")

    def get_average_processing_time(self) -> float:
        """Get average processing time for this stage"""
        if not self.enable_timing:
            return 0.0

        if self.processed_count > 0:
            return self.total_processing_time / self.processed_count
        return 0.0

    def clear_input_queue(self) -> None:
        """Clear the input queue"""
        while not self.input_queue.empty():
            self.input_queue.get()
