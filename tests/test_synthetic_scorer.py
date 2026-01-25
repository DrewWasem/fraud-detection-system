"""Tests for synthetic identity scorer."""

import pytest
from src.detection.synthetic_scorer import SyntheticScorer


class TestSyntheticScorer:
    """Test cases for synthetic scoring."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = SyntheticScorer()

    def test_low_risk_identity(self):
        """Test scoring for low-risk identity."""
        result = self.scorer.score(
            identity_id="test-123",
            ssn_signals={},
            graph_features={"shared_ssn_count": 0},
            velocity_signals={"address_velocity_score": 0.1},
            credit_behavior={"is_thin_file": False},
            device_signals={},
        )

        assert result.score < 0.3
        assert result.risk_level in ["minimal", "low"]
        assert len(result.triggered_signals) == 0

    def test_high_risk_ssn_mismatch(self):
        """Test scoring with SSN-DOB mismatch."""
        result = self.scorer.score(
            identity_id="test-456",
            ssn_signals={"ssn_dob_mismatch": True},
            graph_features={},
            velocity_signals={},
            credit_behavior={},
            device_signals={},
        )

        assert result.score > 0.3
        assert "SSN_DOB_MISMATCH" in result.triggered_signals

    def test_high_risk_shared_ssn(self):
        """Test scoring with shared SSN."""
        result = self.scorer.score(
            identity_id="test-789",
            ssn_signals={},
            graph_features={"shared_ssn_count": 2},
            velocity_signals={},
            credit_behavior={},
            device_signals={},
        )

        assert "SHARED_SSN" in result.triggered_signals

    def test_critical_risk_multiple_signals(self):
        """Test scoring with multiple high-risk signals."""
        result = self.scorer.score(
            identity_id="test-critical",
            ssn_signals={"ssn_dob_mismatch": True, "multiple_ssns": True},
            graph_features={"shared_ssn_count": 1, "cluster_size": 10},
            velocity_signals={"phone_velocity_score": 0.8},
            credit_behavior={"is_thin_file": True, "au_abuse_pattern": True},
            device_signals={"known_fraud_device": True},
        )

        assert result.score > 0.7
        assert result.risk_level in ["high", "critical"]
        assert len(result.triggered_signals) > 3

    def test_explanation_generated(self):
        """Test that explanation is generated."""
        result = self.scorer.score(
            identity_id="test-explanation",
            ssn_signals={"ssn_dob_mismatch": True},
            graph_features={},
            velocity_signals={},
            credit_behavior={},
            device_signals={},
        )

        assert result.explanation is not None
        assert len(result.explanation) > 0
