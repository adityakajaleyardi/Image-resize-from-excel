"""Pure processing logic.

Nothing in this package may import FastAPI or any other web dependency, so that
the command line entry point keeps working on its own.
"""

from .config import ProcessingConfig
from .engine import Event, ProcessingError, RunSummary, run
from .validation import ValidationError, validate_property_hmy_csv, validate_source_csv

__all__ = [
    "Event",
    "ProcessingConfig",
    "ProcessingError",
    "RunSummary",
    "ValidationError",
    "run",
    "validate_property_hmy_csv",
    "validate_source_csv",
]
