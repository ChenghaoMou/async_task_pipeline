"""
Async CPU-Intensive Task Pipeline with Thread-based Pipeline Parallelism
Generic framework for streaming data through CPU-intensive processing stages
"""

import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
import logging
import time

from async_task_pipeline.base.pipeline import AsyncTaskPipeline
from async_task_pipeline.utils import log_pipeline_performance_analysis
from async_task_pipeline.utils import logger

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Async Task Pipeline Example")
    parser.add_argument("--enable-timing", action="store_true", help="Enable timing analysis")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    args = parser.parse_args()
    start_time: float | None = None

    class EndSentinel:
        pass

    def simulate_cpu_intensive_task(
        name: str, processing_time: float, cpu_intensity: int = 1000
    ) -> Callable[[str], str]:
        """Factory for creating simulated CPU-intensive processing functions"""

        def process(data: str) -> str:
            logger.debug(f"{name} processing: {data}")
            end_time = time.perf_counter() + processing_time
            result = 0
            while time.perf_counter() < end_time:
                result += sum(i * i for i in range(cpu_intensity))
            return f"{data} -> {name}[{result % 1000}]"

        return process

    async def example_input_stream(count: int = 10, delay: float = 0.1) -> AsyncIterator[str | EndSentinel]:
        """Example async input stream generator"""
        global start_time

        for i in range(count):
            await asyncio.sleep(delay)
            data = f"chunk_{i}"
            logger.debug(f"Generating input: {data}")
            if i == 0:
                start_time = time.perf_counter()
            yield data

    async def example_output_consumer(output_stream: AsyncIterator[str | EndSentinel | BaseException]) -> None:
        """Example async output consumer"""
        global start_time
        first_result = True
        async for result in output_stream:
            if isinstance(result, EndSentinel):
                logger.debug(f"Sentinel received: {result}")
                break
            if isinstance(result, BaseException):
                logger.error(f"Error: {result}")
                continue
            logger.debug(f"Final output: {result}")
            if first_result:
                first_result = False
                if start_time is not None:
                    logger.info(f"Time to first result: {(time.perf_counter() - start_time) * 1000:.2f}ms")

    async def main(args: argparse.Namespace) -> None:
        """Main function demonstrating the pipeline"""
        global start_time
        logging.basicConfig(
            level=args.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        pipeline = AsyncTaskPipeline[str, EndSentinel | BaseException](
            max_queue_size=500, enable_timing=args.enable_timing, return_exceptions=True
        )
        pipeline.add_stage("DataValidation", simulate_cpu_intensive_task("Validate", 0.010, 500))
        pipeline.add_stage("Transform1", simulate_cpu_intensive_task("Transform1", 0.050, 1500))
        pipeline.add_stage("Transform2", simulate_cpu_intensive_task("Transform2", 0.010, 1000))
        pipeline.add_stage("Serialize", simulate_cpu_intensive_task("Serialize", 0.005, 500))
        await pipeline.start()

        inp_task = asyncio.create_task(pipeline.process_input_stream(example_input_stream(50, 0.01)))
        inp_task.add_done_callback(lambda _: pipeline.put_input_sentinel(EndSentinel()))

        out_task = asyncio.create_task(example_output_consumer(pipeline.generate_output_stream()))
        tasks = [
            inp_task,
            out_task,
        ]
        await asyncio.gather(*tasks)
        await pipeline.stop()

        if start_time is not None:
            logger.info(f"End-to-end latency: {(time.perf_counter() - start_time):.3f}s")
        log_pipeline_performance_analysis(pipeline)

    asyncio.run(main(args))
