"""Tests for velocity analyzer."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.detection.velocity_analyzer import VelocityAnalyzer, VelocityAnalysis, ElementVelocity


class TestVelocityAnalyzer:
    """Test VelocityAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer without Redis."""
        return VelocityAnalyzer(redis_client=None)

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = MagicMock()
        mock.zcount.return_value = 0
        mock.hgetall.return_value = {}
        mock.pipeline.return_value.__enter__ = MagicMock(return_value=mock)
        mock.pipeline.return_value.__exit__ = MagicMock(return_value=None)
        return mock

    @pytest.fixture
    def analyzer_with_redis(self, mock_redis):
        """Create analyzer with mock Redis."""
        return VelocityAnalyzer(redis_client=mock_redis)

    def test_analyze_no_redis(self, analyzer):
        """Test analysis returns zero scores without Redis."""
        result = analyzer.analyze(
            identity_id="test-id",
            ssn_hash="ssn-hash",
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email_hash="email-hash",
        )

        assert isinstance(result, VelocityAnalysis)
        assert result.identity_id == "test-id"
        assert result.address_velocity == 0.0
        assert result.phone_velocity == 0.0
        assert result.email_velocity == 0.0
        assert result.device_velocity == 0.0
        assert result.overall_velocity_score == 0.0
        assert result.risk_level == "minimal"
        assert result.anomalies == []

    def test_analyze_with_device(self, analyzer):
        """Test analysis with device fingerprint."""
        result = analyzer.analyze(
            identity_id="test-id",
            ssn_hash="ssn-hash",
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email_hash="email-hash",
            device_fingerprint="device-fp",
        )

        assert result.device_velocity == 0.0

    def test_calculate_overall_score(self, analyzer):
        """Test overall score calculation."""
        # Test with all zeros
        score = analyzer._calculate_overall_score(0.0, 0.0, 0.0, 0.0)
        assert score == 0.0

        # Test with high values
        score = analyzer._calculate_overall_score(1.0, 1.0, 1.0, 1.0)
        assert score == 1.0

        # Test weighted calculation
        # address: 0.25, phone: 0.35, email: 0.20, device: 0.20
        score = analyzer._calculate_overall_score(0.5, 0.0, 0.0, 0.0)
        assert score == 0.125  # 0.5 * 0.25

    def test_identify_anomalies(self, analyzer):
        """Test anomaly identification."""
        # No anomalies for low velocity
        anomalies = analyzer._identify_anomalies(0.3, 0.3, 0.3, 0.3)
        assert len(anomalies) == 0

        # High address velocity
        anomalies = analyzer._identify_anomalies(0.6, 0.0, 0.0, 0.0)
        assert "HIGH_ADDRESS_VELOCITY" in anomalies

        # High phone velocity
        anomalies = analyzer._identify_anomalies(0.0, 0.6, 0.0, 0.0)
        assert "HIGH_PHONE_VELOCITY" in anomalies

        # Address-phone correlation
        anomalies = analyzer._identify_anomalies(0.4, 0.4, 0.0, 0.0)
        assert "ADDRESS_PHONE_CORRELATION" in anomalies

        # Shared device
        anomalies = analyzer._identify_anomalies(0.0, 0.0, 0.0, 0.6)
        assert "SHARED_DEVICE" in anomalies

    def test_determine_risk_level(self, analyzer):
        """Test risk level determination."""
        assert analyzer._determine_risk_level(0.0, []) == "minimal"
        assert analyzer._determine_risk_level(0.15, []) == "minimal"
        assert analyzer._determine_risk_level(0.25, []) == "low"
        assert analyzer._determine_risk_level(0.45, []) == "medium"
        assert analyzer._determine_risk_level(0.65, []) == "high"
        assert analyzer._determine_risk_level(0.85, []) == "critical"

        # With anomalies
        assert analyzer._determine_risk_level(0.1, ["A"]) == "low"
        assert analyzer._determine_risk_level(0.1, ["A", "B"]) == "medium"
        assert analyzer._determine_risk_level(0.1, ["A", "B", "C"]) == "high"
        assert analyzer._determine_risk_level(0.1, ["A", "B", "C", "D"]) == "critical"

    def test_record_element_use_no_redis(self, analyzer):
        """Test recording without Redis doesn't error."""
        # Should just log debug, not error
        analyzer.record_element_use(
            element_type="address",
            element_hash="addr-hash",
            identity_hash="id-hash",
            ssn_hash="ssn-hash",
        )

    def test_record_element_use_with_redis(self, analyzer_with_redis, mock_redis):
        """Test recording with Redis."""
        pipe_mock = MagicMock()
        mock_redis.pipeline.return_value = pipe_mock
        pipe_mock.execute.return_value = None

        analyzer_with_redis.record_element_use(
            element_type="address",
            element_hash="addr-hash",
            identity_hash="id-hash",
            ssn_hash="ssn-hash",
        )

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()

    def test_record_identity_elements(self, analyzer):
        """Test recording all elements at once."""
        analyzer.record_identity_elements(
            identity_hash="id-hash",
            ssn_hash="ssn-hash",
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email_hash="email-hash",
            device_fingerprint="device-fp",
        )
        # Should not raise

    def test_get_element_history_no_redis(self, analyzer):
        """Test history retrieval without Redis."""
        history = analyzer.get_element_history("address", "addr-hash")

        assert history["identities"] == []
        assert history["ssns"] == []
        assert history["first_seen"] is None
        assert history["last_seen"] is None

    def test_cleanup_no_redis(self, analyzer):
        """Test cleanup without Redis returns 0."""
        removed = analyzer.cleanup_old_data("address")
        assert removed == 0

    def test_element_velocity_calculation(self, analyzer):
        """Test element velocity score calculation."""
        # Create mock velocity data
        velocity = ElementVelocity(
            element_hash="test",
            element_type="address",
            unique_identities_30d=2,
            unique_identities_90d=3,
            unique_identities_180d=5,
            unique_ssns_30d=2,
            unique_ssns_90d=3,
            unique_ssns_180d=5,
            first_seen=None,
            last_seen=None,
            velocity_score=0.0,
        )

        score = analyzer._calculate_element_score("address", velocity)
        assert 0.0 <= score <= 1.0

    def test_high_velocity_element_score(self, analyzer):
        """Test high velocity yields high score."""
        # Above threshold velocity
        velocity = ElementVelocity(
            element_hash="test",
            element_type="address",
            unique_identities_30d=10,
            unique_identities_90d=15,
            unique_identities_180d=20,  # Well above threshold of 5
            unique_ssns_30d=8,
            unique_ssns_90d=12,
            unique_ssns_180d=15,
            first_seen=None,
            last_seen=None,
            velocity_score=0.0,
        )

        score = analyzer._calculate_element_score("address", velocity)
        assert score > 0.5  # Should be high

    def test_low_velocity_element_score(self, analyzer):
        """Test low velocity yields low score."""
        velocity = ElementVelocity(
            element_hash="test",
            element_type="address",
            unique_identities_30d=0,
            unique_identities_90d=1,
            unique_identities_180d=1,  # Just one identity
            unique_ssns_30d=0,
            unique_ssns_90d=1,
            unique_ssns_180d=1,
            first_seen=None,
            last_seen=None,
            velocity_score=0.0,
        )

        score = analyzer._calculate_element_score("address", velocity)
        assert score == 0.0  # Single identity should be 0


class TestVelocityAnalysisIntegration:
    """Integration tests for velocity analysis flow."""

    def test_full_analysis_flow_no_redis(self):
        """Test complete analysis without Redis."""
        analyzer = VelocityAnalyzer(redis_client=None)

        # First record some elements
        analyzer.record_identity_elements(
            identity_hash="id1",
            ssn_hash="ssn1",
            address_hash="addr1",
            phone_hash="phone1",
            email_hash="email1",
        )

        # Then analyze
        result = analyzer.analyze(
            identity_id="test-id",
            ssn_hash="ssn1",
            address_hash="addr1",
            phone_hash="phone1",
            email_hash="email1",
        )

        # Without Redis, should return zeros
        assert result.overall_velocity_score == 0.0
        assert result.risk_level == "minimal"
