"""Async Task Pipeline - A framework for processing streaming data through CPU-intensive tasks.

This package provides a high-performance framework for building data processing
pipelines that combine async I/O for input/output operations with thread-based
processing for CPU-intensive tasks.

Key Components
--------------
AsyncTaskPipeline : Main pipeline orchestrator
    Manages the overall pipeline execution and data flow.
PipelineStage : Individual processing stage
    Represents a single processing step in the pipeline.
PipelineItem : Data container
    Wraps data items with timing and sequence information.

Examples
--------
Basic pipeline usage:

>>> import asyncio
>>> from async_task_pipeline import AsyncTaskPipeline
>>>
>>> async def main():
...     pipeline = AsyncTaskPipeline(enable_timing=True)
...     pipeline.add_stage("double", lambda x: x * 2)
...     pipeline.add_stage("filter", lambda x: x if x > 5 else None)
...
...     await pipeline.start()
...
...     # Process some data
...     async def data_source():
...         for i in range(10):
...             yield i
...
...     await pipeline.process_input_stream(data_source())
...
...     results = []
...     async for result in pipeline.generate_output_stream():
...         results.append(result)
...
...     await pipeline.stop()
...     return results
>>>
>>> # asyncio.run(main())
"""

from .base.item import PipelineItem
from .base.pipeline import AsyncTaskPipeline
from .base.stage import PipelineStage
from .utils import DetailedTiming
from .utils import log_pipeline_performance_analysis
from .utils import logger

__version__ = "0.1.10"
__all__ = [
    "__version__",
    "AsyncTaskPipeline",
    "PipelineStage",
    "PipelineItem",
    "logger",
    "log_pipeline_performance_analysis",
    "DetailedTiming",
]
