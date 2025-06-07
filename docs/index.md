# Async Task Pipeline

A Python framework for processing streaming data through computation-intensive tasks with an async I/O layer.
## Overview

The Async Task Pipeline framework provides a flexible and efficient way to build data processing pipelines that can handle streaming data with computation-intensive tasks. It combines the benefits of async I/O for handling input/output operations with thread-based processing for compute-bound work.

## Key Features

- **Async I/O Integration**: Seamlessly handle async input and output
- **Thread-based Processing**: Compute-intensive tasks run in separate threads
- **Performance Monitoring**: Built-in timing and latency analysis
- **Pipeline Composition**: Chain multiple processing tasks together with stages
- **Error Handling**: Robust error handling and logging
- **Memory Efficient**: Queue-based processing with configurable limits

## Quick Start

```python
import asyncio
from async_task_pipeline import AsyncTaskPipeline

# Create a pipeline
pipeline = AsyncTaskPipeline(max_queue_size=100, enable_timing=True)

# Add processing stages
pipeline.add_stage("process", lambda x: x * 2)
pipeline.add_stage("filter", lambda x: x if x > 10 else None)

# Start the pipeline
await pipeline.start()

# Process data
async def data_generator():
    for i in range(20):
        yield i
        await asyncio.sleep(0.1)

# Process input stream and collect results
await pipeline.process_input_stream(data_generator())

results = []
async for result in pipeline.generate_output_stream():
    results.append(result)

# Get performance statistics
stats = pipeline.get_latency_summary()
print(f"Processed {stats['total_items']} items")
print(f"Average latency: {stats['avg_total_latency']:.3f}s")

# Stop the pipeline
await pipeline.stop()
```

## Architecture

The framework is built around three main components:

1. **AsyncTaskPipeline**: Main orchestrator that manages stages and data flow
2. **PipelineStage**: Individual processing stages that run in separate threads
3. **PipelineItem**: Data containers that track timing and flow through the pipeline

### Pipeline Workflow

The following diagram illustrates how data flows through the pipeline with parallel processing across multiple stages:

```mermaid
sequenceDiagram
    participant Input as Async Input Stream
    participant Main as Main Thread<br/>(Asyncio Event Loop)
    participant Q1 as Input Queue
    participant T1 as Thread 1<br/>(Stage 1: Task 1)
    participant Q2 as Queue 1
    participant T2 as Thread 2<br/>(Stage 2: Task 2)
    participant Q3 as Queue 2
    participant T3 as Thread 3<br/>(Stage 3: Task 3)
    participant Q4 as Output Queue
    participant Output as Async Output Stream

    Note over Main: Pipeline Parallelism - Multiple items processed simultaneously

    Input->>Main: yield Item A
    Main->>Q1: put Item A
    Q1->>T1: get Item A

    Input->>Main: yield Item B
    Main->>Q1: put Item B
    Q1->>T1: get Item B

    par Item A flows through pipeline
        T1->>Q2: put processed Item A
        Q2->>T2: get Item A
        T2->>Q3: put processed Item A
        Q3->>T3: get Item A
        T3->>Q4: put processed Item A
    and Item B follows behind
        T1->>Q2: put processed Item B
        Q2->>T2: get Item B
        T2->>Q3: put processed Item B
    and Item C enters pipeline
        Input->>Main: yield Item C
        Main->>Q1: put Item C
        Q1->>T1: get Item C
        T1->>Q2: put processed Item C
    end

    Q4->>Main: get Item A
    Main->>Output: yield Item A

    Q4->>Main: get Item B
    Main->>Output: yield Item B

```

The asyncio event loop handles I/O operations while each pipeline stage runs in its own thread for parallelism. This design enables:

- **Pipeline Parallelism**: Multiple items can be processed simultaneously at different stages
- **Async I/O**: Non-blocking input and output operations
- **Compute Efficiency**: Parallelism for CPU-bound tasks through threading (Well, still bound by GIL 🤷️)

## Installation

```bash
pip install async-task-pipeline
```

## Next Steps

- Check out the [API Reference](api/pipeline.md) for detailed documentation
- Explore the pipeline components: [Pipeline](api/pipeline.md), [Stage](api/stage.md), [Item](api/item.md)
- Learn about [utilities](api/utils.md) for performance analysis and logging
