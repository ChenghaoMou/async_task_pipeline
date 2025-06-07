"""Pydantic models for pipeline performance analysis data structures."""

from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class EfficiencyMetrics(BaseModel):
    """Overall efficiency metrics for pipeline performance.

    Represents the ratio between actual computation time and total
    processing time, providing insights into pipeline overhead.

    Parameters
    ----------
    computation_efficiency : float
        Ratio of actual computation time to total latency (0.0 to 1.0).
    overhead_ratio : float
        Ratio of overhead time (queuing, transmission) to total latency (0.0 to 1.0).
    """

    computation_efficiency: float = Field(..., ge=0.0, le=1.0, description="Ratio of computation time to total latency")
    overhead_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of overhead time to total latency")


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown for a pipeline stage.

    Provides granular timing metrics for different phases of
    stage processing including computation, queuing, and transmission.

    Parameters
    ----------
    avg_computation_time : float
        Average time spent in actual computation (seconds).
    avg_queue_wait_time : float
        Average time spent waiting in input queue (seconds).
    avg_transmission_time : float
        Average time spent transmitting to next stage (seconds).
    computation_ratio : float
        Ratio of computation time to total stage processing time.
    """

    avg_computation_time: float = Field(..., ge=0.0, description="Average computation time in seconds")
    avg_queue_wait_time: float = Field(..., ge=0.0, description="Average queue wait time in seconds")
    avg_transmission_time: float = Field(..., ge=0.0, description="Average transmission time in seconds")
    computation_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of computation time to total stage time")


class StageStatistics(BaseModel):
    """Performance statistics for a single pipeline stage.

    Comprehensive metrics for individual pipeline stages including
    throughput, latency distribution, and detailed timing breakdowns.

    Parameters
    ----------
    avg_latency : float
        Average latency for this stage (seconds).
    min_latency : float
        Minimum latency observed for this stage (seconds).
    max_latency : float
        Maximum latency observed for this stage (seconds).
    processed_count : int
        Total number of items processed by this stage.
    avg_processing_time : float
        Average processing time reported by the stage (seconds).
    timing_breakdown : TimingBreakdown
        Detailed timing breakdown for this stage.
    """

    avg_latency: float = Field(..., ge=0.0, description="Average stage latency in seconds")
    min_latency: float = Field(..., ge=0.0, description="Minimum stage latency in seconds")
    max_latency: float = Field(..., ge=0.0, description="Maximum stage latency in seconds")
    processed_count: int = Field(..., ge=0, description="Number of items processed by this stage")
    avg_processing_time: float = Field(..., ge=0.0, description="Average processing time in seconds")
    timing_breakdown: TimingBreakdown = Field(..., description="Detailed timing breakdown for this stage")


class LatencySummary(BaseModel):
    """Complete pipeline latency and performance summary.

    Comprehensive performance analysis for the entire pipeline including
    overall metrics, per-stage breakdowns, and efficiency analysis.

    Parameters
    ----------
    total_items : int
        Total number of items that completed processing.
    avg_total_latency : float
        Average end-to-end latency across all items (seconds).
    min_total_latency : float
        Minimum end-to-end latency observed (seconds).
    max_total_latency : float
        Maximum end-to-end latency observed (seconds).
    stage_statistics : Dict[str, StageStatistics]
        Per-stage performance statistics keyed by stage name.
    overall_efficiency : EfficiencyMetrics
        Overall pipeline efficiency metrics.
    """

    total_items: int = Field(..., ge=0, description="Total number of completed items")
    avg_total_latency: float = Field(..., ge=0.0, description="Average end-to-end latency in seconds")
    min_total_latency: float = Field(..., ge=0.0, description="Minimum end-to-end latency in seconds")
    max_total_latency: float = Field(..., ge=0.0, description="Maximum end-to-end latency in seconds")
    stage_statistics: Dict[str, StageStatistics] = Field(..., description="Per-stage performance statistics")
    overall_efficiency: EfficiencyMetrics = Field(..., description="Overall pipeline efficiency metrics")


class ItemTimingTotals(BaseModel):
    """Total timing metrics for an individual pipeline item.

    Aggregated timing information for a single item's journey
    through the entire pipeline.

    Parameters
    ----------
    total_computation_time : float
        Total time spent in actual computation across all stages (seconds).
    total_overhead_time : float
        Total time spent in overhead (queuing, transmission) (seconds).
    total_latency : float
        Total end-to-end latency for this item (seconds).
    computation_ratio : float
        Ratio of computation time to total latency for this item.
    """

    total_computation_time: float = Field(..., ge=0.0, description="Total computation time in seconds")
    total_overhead_time: float = Field(..., ge=0.0, description="Total overhead time in seconds")
    total_latency: float = Field(..., ge=0.0, description="Total end-to-end latency in seconds")
    computation_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of computation time to total latency")


class StageTimingDetail(BaseModel):
    """Detailed timing for a single stage within an item's processing.

    Granular timing information for how a specific item was processed
    by a particular pipeline stage.

    Parameters
    ----------
    queue_wait_time : float
        Time spent waiting in the stage's input queue (seconds).
    computation_time : float
        Time spent in actual computation for this stage (seconds).
    transmission_time : float
        Time spent transmitting to the next stage (seconds).
    total_stage_time : float
        Total time for this stage (sum of above times) (seconds).
    """

    queue_wait_time: float = Field(..., ge=0.0, description="Queue wait time in seconds")
    computation_time: float = Field(..., ge=0.0, description="Computation time in seconds")
    transmission_time: float = Field(..., ge=0.0, description="Transmission time in seconds")
    total_stage_time: float = Field(..., ge=0.0, description="Total stage processing time in seconds")


class ItemTimingBreakdown(BaseModel):
    """Complete timing breakdown for an individual pipeline item.

    Comprehensive timing analysis for a single item including
    per-stage breakdowns and aggregated totals.

    Parameters
    ----------
    totals : ItemTimingTotals
        Aggregated timing totals for this item.
    stages : Dict[str, StageTimingDetail], optional
        Per-stage timing details keyed by stage name.
    """

    totals: ItemTimingTotals = Field(..., description="Aggregated timing totals")
    stages: Optional[Dict[str, StageTimingDetail]] = Field(None, description="Per-stage timing details")


class PipelineAnalysis(BaseModel):
    """Complete pipeline performance analysis.

    Top-level model that encompasses all pipeline performance analysis
    including summary statistics and detailed item breakdowns.

    Parameters
    ----------
    summary : LatencySummary
        Overall pipeline performance summary.
    item_breakdowns : Dict[int, ItemTimingBreakdown], optional
        Detailed timing breakdowns for individual items keyed by sequence number.
    analysis_metadata : Dict[str, Any], optional
        Additional metadata about the analysis (timestamps, configuration, etc.).
    """

    summary: LatencySummary = Field(..., description="Overall pipeline performance summary")
    item_breakdowns: Optional[list[ItemTimingBreakdown]] = Field(
        None, description="Detailed timing breakdowns for individual items"
    )
    analysis_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional analysis metadata")
