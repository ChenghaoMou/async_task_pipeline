# Async CPU-Intensive Task Pipeline

[![PyPI](https://img.shields.io/pypi/v/async_task_pipeline.svg?style=flat-square)](https://pypi.python.org/pypi/async_task_pipeline) [![PyPI](https://img.shields.io/pypi/l/async_task_pipeline.svg?style=flat-square)](https://pypi.python.org/pypi/async_task_pipeline) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/async_task_pipeline)


A framework for processing streaming data through CPU-intensive tasks while maintaining order and tracking latency.


## Overview

Combines async I/O with threaded CPU processing:
- **Async streams**: Non-blocking input/output
- **Pipeline parallelism**: Each stage runs in its own thread
- **Latency tracking**: Monitor end-to-end and per-stage performance
- Documentation: [Github Pages](https://chenghaomou.github.io/async_task_pipeline/)

## Workflow

```mermaid
sequenceDiagram
    participant Input as Async Input Stream
    participant Main as Main Thread<br/>(Asyncio Event Loop)
    participant Q1 as Input Queue
    participant T1 as Thread 1<br/>(Stage 1: Validate)
    participant Q2 as Queue 1
    participant T2 as Thread 2<br/>(Stage 2: Transform)
    participant Q3 as Queue 2
    participant T3 as Thread 3<br/>(Stage 3: Serialize)
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

The asyncio event loop handles I/O operations while each pipeline stage runs in its own thread for true CPU parallelism.

## Quick Start

```python
import asyncio
from async_task_pipeline import AsyncTaskPipeline

# Create pipeline
pipeline = AsyncTaskPipeline(max_queue_size=100)

# Add processing stages
pipeline.add_stage("validate", validate_function)
pipeline.add_stage("transform", transform_function)
pipeline.add_stage("serialize", serialize_function)

# Start and run
await pipeline.start()

# Process streams concurrently
await asyncio.gather(
    pipeline.process_input_stream(your_input_stream()),
    consume_output(pipeline.generate_output_stream())
)

await pipeline.stop()
```

## Usage Patterns

### Basic Processing Function
```python
def cpu_intensive_task(data):
    # Your CPU-heavy computation here
    result = complex_computation(data)
    return result
```

### Input Stream
```python
async def input_stream():
    for item in data_source:
        yield item
        await asyncio.sleep(0)  # Yield control
```

### Output Consumer
```python
async def consume_output(output_stream):
    async for result in output_stream:
        # Handle processed result
        print(f"Processed: {result}")
```

## Pipeline Management

```python
# Clear pipeline state
pipeline.clear()

# Stop gracefully
await pipeline.stop()

# Get performance metrics
summary = pipeline.get_latency_summary()
```

## Running the Example

```bash
python example.py --enable-timing
```

The example demonstrates a 4-stage pipeline processing 50 items with simulated CPU-intensive tasks.

## Development

This project uses modern Python development tools managed through a Makefile and `uv`.

### Quick Setup

```bash
# Install development dependencies and set up pre-commit hooks
make dev-setup

# Run all quality checks
make check
```

### Available Commands

```bash
# Development setup
make install          # Install the package
make install-dev      # Install with development dependencies
make dev-setup        # Complete development environment setup

# Code quality
make format           # Format code with ruff
make lint             # Lint code with ruff
make type-check       # Run type checking with mypy
make test             # Run tests with pytest
make test-cov         # Run tests with coverage
make check            # Run all quality checks

# Pre-commit
make pre-commit-install  # Install pre-commit hooks
make pre-commit         # Run pre-commit on all files

# Building and publishing
make build            # Build the package
make publish-test     # Publish to TestPyPI
make publish          # Publish to PyPI

# Version management
make version-patch    # Bump patch version
make version-minor    # Bump minor version
make version-major    # Bump major version

# Utilities
make clean            # Clean up cache and build files
make watch-test       # Run tests in watch mode
make help             # Show all available commands
```

### Code Quality Standards

This project enforces high code quality standards:

- **Formatting**: `ruff format` for consistent code style
- **Linting**: `ruff check` for code quality and best practices
- **Type Checking**: `mypy` for static type analysis
- **Testing**: `pytest` with coverage reporting
- **Pre-commit hooks**: Automated checks before each commit
- **Security**: `bandit` for security vulnerability scanning

### Publishing Workflow

1. Make your changes and ensure all tests pass:
   ```bash
   make check
   ```

2. Bump the version:
   ```bash
   make version-patch  # or version-minor/version-major
   ```

3. Build and publish:
   ```bash
   make publish  # or publish-test for TestPyPI
   ```

## When to Use

- Streaming data with CPU-heavy processing
- Need to maintain input order in output
- Want pipeline parallelism (different stages processing different items)
- CPU processing is with libraries that release Python's GIL (NumPy, PyTorch, etc.)
