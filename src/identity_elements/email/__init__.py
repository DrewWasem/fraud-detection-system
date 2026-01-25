"""Email analysis module."""

from .domain_analyzer import DomainAnalyzer
from .pattern_detector import EmailPatternDetector
from .age_estimator import EmailAgeEstimator

__all__ = ["DomainAnalyzer", "EmailPatternDetector", "EmailAgeEstimator"]
