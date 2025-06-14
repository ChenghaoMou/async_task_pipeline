from collections.abc import Callable
import queue
import threading
import time
import types

from returns.pipeline import is_successful
from returns.result import ResultE
from returns.result import safe

from async_task_pipeline.base.item import PipelineItem
from async_task_pipeline.utils import logger
from async_task_pipeline.utils.metrics import DetailedTiming


class EndSignal:
    pass


class PipelineStage:
    """Single stage in the CPU-intensive task pipeline.

    Represents an individual processing stage that runs in its own thread
    and processes items from an input queue, applying a transformation
    function, and placing results in an output queue.

    Parameters
    ----------
    name : str
        Unique identifier for this stage, used in logging and timing analysis.
    process_fn : Callable
        Function to process data items. Should be thread-safe and accept
        a single argument, returning processed data, None (to filter), or
        a generator (for multiple outputs).
    input_queue : queue.Queue
        Queue from which to read input items for processing.
    output_queue : queue.Queue
        Queue to which processed items are written.
    enable_timing : bool, default=True
        Whether to collect detailed timing information for this stage.
    """

    def __init__(
        self,
        name: str,
        process_fn: Callable,
        input_queue: queue.Queue,
        output_queue: queue.Queue,
        enable_timing: bool = True,
        return_exceptions: bool = False,
    ):
        self.name = name
        self.process_fn = safe(process_fn)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.thread: threading.Thread | None = None
        self.running = False
        self.processed_count = 0
        self.total_processing_time = 0.0
        self.enable_timing = enable_timing
        self.return_exceptions = return_exceptions

    def start(self) -> None:
        """Start the worker thread for this stage.

        Creates and starts a daemon thread that will continuously process
        items from the input queue until stopped.

        Notes
        -----
        The worker thread is marked as daemon so it won't prevent the
        program from exiting.
        """
        self.running = True
        self.thread = threading.Thread(target=self._worker, name=f"Stage-{self.name}")
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started pipeline stage: {self.name}")

    def stop(self) -> None:
        """Stop the worker thread.

        Signals the worker thread to stop and waits for it to complete.
        Sends a sentinel value (None) to the input queue to wake up the
        worker if it's waiting.

        Notes
        -----
        This method blocks until the worker thread has fully stopped.
        """
        self.running = False
        self.input_queue.put(EndSignal())
        if self.thread:
            self.thread.join()
        logger.info(f"Stopped pipeline stage: {self.name}")

    def _worker(self) -> None:
        """Worker thread that processes items from input queue"""
        while self.running:
            try:
                item = self.input_queue.get(timeout=1.0)
                if isinstance(item, EndSignal):
                    break
                if not isinstance(item, PipelineItem):
                    self.output_queue.put(item)
                    continue

                item.enable_timing = self.enable_timing
                processing_start_time = time.perf_counter()
                item.record_entry_time(self.name)
                res: ResultE = self.process_fn(item.data)

                if not is_successful(res):
                    if self.return_exceptions:
                        logger.error(f"Error in {self.name}: {res.failure()}")
                        self.output_queue.put(res.failure())
                    continue

                result_data = res.unwrap()
                if result_data is None:
                    continue

                processing_end_time = time.perf_counter()
                if isinstance(result_data, types.GeneratorType):
                    try:
                        for result in result_data:
                            new_item = item.model_copy()
                            new_item.data = result
                            new_item.record_completion_time(self.name)
                            self.output_queue.put(new_item)
                    except BaseException as e:
                        if self.return_exceptions:
                            self.output_queue.put(e)
                        continue
                else:
                    item.data = result_data
                    item.record_completion_time(self.name)
                    self.output_queue.put(item)

                transmission_end = time.perf_counter()

                if self.enable_timing:
                    detailed_timing = DetailedTiming(
                        queue_enter_time=item.get_entry_time(self.name),
                        processing_start_time=processing_start_time,
                        processing_end_time=processing_end_time,
                        queue_exit_time=transmission_end,
                    )
                    item.record_detailed_timing(self.name, detailed_timing)

                    process_time = processing_end_time - processing_start_time
                    self.total_processing_time += process_time

                    logger.debug(
                        f"{self.name} processed item: "
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
        """Get average processing time for this stage.

        Calculates the average time spent in the processing function
        across all processed items.

        Returns
        -------
        float
            Average processing time in seconds, or 0.0 if timing is disabled
            or no items have been processed.
        """
        if not self.enable_timing:
            return 0.0

        if self.processed_count > 0:
            return self.total_processing_time / self.processed_count
        return 0.0

    def clear_input_queue(self) -> None:
        """Clear the input queue"""
        while not self.input_queue.empty():
            self.input_queue.get()
