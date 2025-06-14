"""
Performance analysis utilities for async task pipeline
"""

from typing import TYPE_CHECKING

from .logging import logger

if TYPE_CHECKING:  # pragma: no cover
    from ..base.pipeline import AsyncTaskPipeline


def log_pipeline_performance_analysis(pipeline: "AsyncTaskPipeline") -> None:  # pragma: no cover
    """Log comprehensive performance analysis for an AsyncTaskPipeline.

    Analyzes pipeline performance and logs detailed metrics including overall
    efficiency, per-stage breakdowns, and individual item timing analysis.
    This function is useful for identifying bottlenecks and optimizing
    pipeline performance.

    Parameters
    ----------
    pipeline : AsyncTaskPipeline
        The pipeline instance to analyze. Must have timing enabled and
        have processed at least one item.

    Notes
    -----
    This function logs analysis results using the pipeline's logger.
    If timing is disabled on the pipeline, only a warning message is logged.

    Examples
    --------
    >>> pipeline = AsyncTaskPipeline(enable_timing=True)
    >>> # ... process some data ...
    >>> log_pipeline_performance_analysis(pipeline)
    """
    if not pipeline.enable_timing:
        logger.info("Pipeline timing is disabled. No analysis available.")
        return

    summary = pipeline.get_report()
    if summary is None:
        logger.info("No items processed. No analysis available.")
        return

    logger.info("Enhanced Pipeline Performance Analysis:")
    logger.info(f" Total items processed: {summary.summary.total_items}")
    logger.info(f" Average end-to-end latency: {summary.summary.avg_total_latency:.3f}s")

    efficiency = summary.summary.overall_efficiency
    logger.info(" Efficiency Details:")
    logger.info(f"  Computation efficiency: {efficiency.computation_efficiency:.1%}")
    logger.info(f"  Overhead ratio: {efficiency.overhead_ratio:.1%}")

    logger.info(" Per-Stage Performance Breakdown:")
    for stage_name, stats in summary.summary.stage_statistics.items():
        timing = stats.timing_breakdown
        logger.info(f" - {stage_name}:")
        logger.info(f"   Processed: {stats.processed_count} items")
        logger.info(f"   Avg computation time: {timing.avg_computation_time * 1000:.2f}ms")
        logger.info(f"   Avg queue wait time: {timing.avg_queue_wait_time * 1000:.2f}ms")
        logger.info(f"   Avg transmission time: {timing.avg_transmission_time * 1000:.2f}ms")
        logger.info(f"   Computation ratio: {timing.computation_ratio:.1%}")

    if summary.item_breakdowns is None:
        logger.info("No item breakdowns available.")
        return

    logger.info(" Detailed Analysis for First Few Items:")
    for item in summary.item_breakdowns[:3]:
        logger.info(" - Item:")
        totals = item.totals
        logger.info(f"   Total latency: {totals.total_latency * 1000:.2f}ms")
        logger.info(f"   Actual computation time: {totals.total_computation_time * 1000:.2f}ms")
        logger.info(f"   Actual overhead time: {totals.total_overhead_time * 1000:.2f}ms")
        logger.info(f"   Computation ratio: {totals.computation_ratio:.1%}")
