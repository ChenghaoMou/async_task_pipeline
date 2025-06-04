"""
Async CPU-Intensive Task Pipeline with Thread-based Pipeline Parallelism
Generic framework for streaming data through CPU-intensive processing stages
"""

import asyncio
from collections.abc import AsyncIterator
from collections.abc import Callable
import logging
import time
from typing import Any

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

    class Sentinel:
        pass

    def simulate_cpu_intensive_task(
        name: str, processing_time: float, cpu_intensity: int = 1000
    ) -> Callable[[Any], Any]:
        """Factory for creating simulated CPU-intensive processing functions"""

        def process(data: Any) -> Any:
            if isinstance(data, Sentinel):
                return data
            logger.debug(f"{name} processing: {data}")
            end_time = time.perf_counter() + processing_time
            result = 0
            while time.perf_counter() < end_time:
                result += sum(i * i for i in range(cpu_intensity))
            return f"{data} -> {name}[{result % 1000}]"

        return process

    async def example_input_stream(count: int = 10, delay: float = 0.1) -> AsyncIterator[str]:
        """Example async input stream generator"""
        global start_time
        for i in range(count):
            await asyncio.sleep(delay)
            data = f"chunk_{i}"
            logger.debug(f"Generating input: {data}")
            yield data
            if i == 0:
                start_time = time.perf_counter()
        yield Sentinel()

    async def example_output_consumer(output_stream: AsyncIterator[Any]) -> None:
        """Example async output consumer"""
        global start_time
        first_result = True
        async for result in output_stream:
            if isinstance(result, Sentinel):
                break
            logger.debug(f"Final output: {result}")
            if first_result:
                first_result = False
                if start_time is not None:
                    logger.info(f"Time to first result: {(time.perf_counter() - start_time) * 1000:.2f}ms")

    async def main(args: argparse.Namespace) -> None:
        """Main function demonstrating the pipeline"""
        logging.basicConfig(
            level=args.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        start_time = time.perf_counter()
        pipeline = AsyncTaskPipeline(max_queue_size=500, enable_timing=args.enable_timing)
        pipeline.add_stage("DataValidation", simulate_cpu_intensive_task("Validate", 0.010, 500))
        pipeline.add_stage("Transform1", simulate_cpu_intensive_task("Transform1", 0.050, 1500))
        pipeline.add_stage("Transform2", simulate_cpu_intensive_task("Transform2", 0.010, 1000))
        pipeline.add_stage("Serialize", simulate_cpu_intensive_task("Serialize", 0.005, 500))
        await pipeline.start()

        tasks = [
            asyncio.create_task(pipeline.process_input_stream(example_input_stream(50, 0.01))),
            asyncio.create_task(example_output_consumer(pipeline.generate_output_stream())),
        ]

        await asyncio.gather(*tasks)
        await pipeline.stop()

        logger.debug(f"Latency: {time.perf_counter() - start_time:.4f}s")
        log_pipeline_performance_analysis(pipeline)

    asyncio.run(main(args))
