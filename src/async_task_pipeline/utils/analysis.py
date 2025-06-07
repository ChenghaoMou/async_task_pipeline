"""
Performance analysis utilities for async task pipeline
"""

import time
from typing import TYPE_CHECKING
from typing import Optional

from .logging import logger
from .models import EfficiencyMetrics
from .models import ItemTimingBreakdown
from .models import ItemTimingTotals
from .models import LatencySummary
from .models import PipelineAnalysis
from .models import StageStatistics
from .models import StageTimingDetail
from .models import TimingBreakdown

if TYPE_CHECKING:
    from ..base.pipeline import AsyncTaskPipeline


def log_pipeline_performance_analysis(pipeline: "AsyncTaskPipeline") -> None:
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

    logger.info("Enhanced Pipeline Performance Analysis:")
    summary = pipeline.get_latency_summary()
    if "total_items" not in summary:
        logger.info("No items processed. No analysis available.")
        return

    logger.info(f"Total items processed: {summary['total_items']}")
    logger.info(f"Average end-to-end latency: {summary['avg_total_latency']:.3f}s")

    efficiency = summary["overall_efficiency"]
    logger.info("Overall Efficiency Metrics:")
    logger.info(f"  Computation efficiency: {efficiency['computation_efficiency']:.1%}")
    logger.info(f"  Overhead ratio: {efficiency['overhead_ratio']:.1%}")

    logger.info("Per-Stage Performance Breakdown:")
    for stage_name, stats in summary["stage_statistics"].items():
        timing = stats["timing_breakdown"]
        logger.info(f"  {stage_name}:")
        logger.info(f"    Processed: {stats['processed_count']} items")
        logger.info(f"    Avg computation time: {timing['avg_computation_time'] * 1000:.2f}ms")
        logger.info(f"    Avg queue wait time: {timing['avg_queue_wait_time'] * 1000:.2f}ms")
        logger.info(f"    Avg transmission time: {timing['avg_transmission_time'] * 1000:.2f}ms")
        logger.info(f"    Computation ratio: {timing['computation_ratio']:.1%}")

    logger.info("Detailed Analysis for First Few Items:")
    for item in pipeline.completed_items[:3]:
        breakdown = item.get_timing_breakdown()
        logger.info(f" Item {item.seq_num}:")

        if breakdown is not None and "totals" in breakdown:
            totals = breakdown["totals"]
            logger.info(f"  Total latency: {totals['total_latency'] * 1000:.2f}ms")
            logger.info(f"  Actual computation time: {totals['total_computation_time'] * 1000:.2f}ms")
            logger.info(f"  Actual overhead time: {totals['total_overhead_time'] * 1000:.2f}ms")
            logger.info(f"  Computation ratio: {totals['computation_ratio']:.1%}")


def get_pipeline_analysis(
    pipeline: "AsyncTaskPipeline", include_item_details: bool = True
) -> Optional[PipelineAnalysis]:
    """Get structured pipeline performance analysis as Pydantic models.

    Converts pipeline performance data into validated Pydantic models for
    structured analysis, serialization, and type-safe processing.

    Parameters
    ----------
    pipeline : AsyncTaskPipeline
        The pipeline instance to analyze. Must have timing enabled and
        have processed at least one item.
    include_item_details : bool, default=True
        Whether to include detailed per-item timing breakdowns in the analysis.

    Returns
    -------
    PipelineAnalysis | None
        Structured analysis data, or None if timing is disabled or no items processed.

    Examples
    --------
    >>> pipeline = AsyncTaskPipeline(enable_timing=True)
    >>> # ... process some data ...
    >>> analysis = get_pipeline_analysis(pipeline)
    >>> print(f"Average latency: {analysis.summary.avg_total_latency:.3f}s")
    >>> print(f"Efficiency: {analysis.summary.overall_efficiency.computation_efficiency:.1%}")
    """
    if not pipeline.enable_timing:
        return None

    summary_data = pipeline.get_latency_summary()
    if "total_items" not in summary_data:
        return None

    stage_stats = {}
    for stage_name, stats in summary_data["stage_statistics"].items():
        timing_data = stats["timing_breakdown"]

        timing_breakdown = TimingBreakdown(
            avg_computation_time=timing_data["avg_computation_time"],
            avg_queue_wait_time=timing_data["avg_queue_wait_time"],
            avg_transmission_time=timing_data["avg_transmission_time"],
            computation_ratio=timing_data["computation_ratio"],
        )

        stage_stats[stage_name] = StageStatistics(
            avg_latency=stats["avg_latency"],
            min_latency=stats["min_latency"],
            max_latency=stats["max_latency"],
            processed_count=stats["processed_count"],
            avg_processing_time=stats["avg_processing_time"],
            timing_breakdown=timing_breakdown,
        )

    efficiency_data = summary_data["overall_efficiency"]
    efficiency = EfficiencyMetrics(
        computation_efficiency=efficiency_data["computation_efficiency"],
        overhead_ratio=efficiency_data["overhead_ratio"],
    )

    summary = LatencySummary(
        total_items=summary_data["total_items"],
        avg_total_latency=summary_data["avg_total_latency"],
        min_total_latency=summary_data["min_total_latency"],
        max_total_latency=summary_data["max_total_latency"],
        stage_statistics=stage_stats,
        overall_efficiency=efficiency,
    )

    item_breakdowns = None
    if include_item_details:
        item_breakdowns = {}
        for item in pipeline.completed_items:
            breakdown_data = item.get_timing_breakdown()
            if breakdown_data and "totals" in breakdown_data:
                totals_data = breakdown_data["totals"]

                totals = ItemTimingTotals(
                    total_computation_time=totals_data["total_computation_time"],
                    total_overhead_time=totals_data["total_overhead_time"],
                    total_latency=totals_data["total_latency"],
                    computation_ratio=totals_data["computation_ratio"],
                )

                stages = {}
                for stage_name, stage_data in breakdown_data.items():
                    if stage_name != "totals" and isinstance(stage_data, dict):
                        stages[stage_name] = StageTimingDetail(
                            queue_wait_time=stage_data["queue_wait_time"],
                            computation_time=stage_data["computation_time"],
                            transmission_time=stage_data["transmission_time"],
                            total_stage_time=stage_data["total_stage_time"],
                        )

                item_breakdowns[item.seq_num] = ItemTimingBreakdown(totals=totals, stages=stages if stages else None)

    analysis_metadata = {
        "analysis_timestamp": time.time(),
        "enable_timing": pipeline.enable_timing,
        "total_stages": len(pipeline.stages),
        "pipeline_running": pipeline.running,
    }

    return PipelineAnalysis(summary=summary, item_breakdowns=item_breakdowns, analysis_metadata=analysis_metadata)
