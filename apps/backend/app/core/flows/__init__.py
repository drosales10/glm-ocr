"""
Módulo de flujos de procesamiento
"""

from app.core.flows.base import TaskProcessingFlow, ProcessingContext, StepProgress, FlowFactory
from app.core.flows.pipeline_flow import PipelineFlow

# Registrar flujos
FlowFactory.register_flow("pipeline", PipelineFlow)

__all__ = [
    "TaskProcessingFlow",
    "ProcessingContext",
    "StepProgress",
    "FlowFactory",
]
