"""Tests for the main module."""

import asyncio
import time
from typing import AsyncIterator
from typing import Callable

import pytest

from async_task_pipeline import AsyncTaskPipeline


@pytest.mark.asyncio
async def test_example() -> None:
    class Sentinel:
        pass

    def simulate_cpu_intensive_task(
        name: str, processing_time: float, cpu_intensity: int = 1000
    ) -> Callable[[str], str]:
        """Factory for creating simulated CPU-intensive processing functions"""

        def process(data: str) -> str:
            if isinstance(data, Sentinel):
                return data
            end_time = time.perf_counter() + processing_time
            result = 0
            while time.perf_counter() < end_time:
                result += sum(i * i for i in range(cpu_intensity))
            return f"{data} -> {name}[{result % 1000}]"

        return process

    async def example_input_stream(count: int = 10, delay: float = 0.1) -> AsyncIterator[str | Sentinel]:
        """Example async input stream generator"""
        for i in range(count):
            await asyncio.sleep(delay)
            yield f"chunk_{i}"

        yield Sentinel()

    async def example_output_consumer(output_stream: AsyncIterator[str | Sentinel]) -> None:
        """Example async output consumer"""
        first_result = True
        async for result in output_stream:
            if isinstance(result, Sentinel):
                break
            if first_result:
                first_result = False

    async def main() -> None:
        """Main function demonstrating the pipeline"""

        pipeline = AsyncTaskPipeline[str, Sentinel](max_queue_size=500, enable_timing=True)
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

    await main()
