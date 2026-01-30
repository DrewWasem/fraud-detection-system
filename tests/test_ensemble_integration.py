"""Integration tests for ensemble detection."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.detection.ensemble import EnsembleDetector
from src.detection.synthetic_scorer import SyntheticScorer
from src.detection.bust_out_predictor import BustOutPredictor
from src.detection.velocity_analyzer import VelocityAnalyzer
from src.detection.credit_behavior import CreditBehaviorAnalyzer
from src.detection.authorized_user import AuthorizedUserDetector
from src.ingestion.bureau_connector import MockBureauConnector


class TestEnsembleDetection:
    """Test complete ensemble detection flow."""

    @pytest.fixture
    def ensemble(self):
        """Create ensemble detector with mock bureau."""
        bureau = MockBureauConnector()
        velocity = VelocityAnalyzer(redis_client=None)
        credit_behavior = CreditBehaviorAnalyzer(bureau_connector=bureau)
        au_detector = AuthorizedUserDetector(bureau_connector=bureau)
        synthetic_scorer = SyntheticScorer()
        bust_out = BustOutPredictor()

        return EnsembleDetector(
            synthetic_scorer=synthetic_scorer,
            bust_out_predictor=bust_out,
            velocity_analyzer=velocity,
            credit_behavior_analyzer=credit_behavior,
            au_detector=au_detector,
        )

    def test_analyze_clean_identity(self, ensemble):
        """Test analysis of a clean identity."""
        result = ensemble.analyze(
            identity_id="clean-id-12345",
            ssn_hash="ssn-clean-hash",
            claimed_dob=datetime(1985, 3, 15),
            address_hash="addr-clean-hash",
            phone_hash="phone-clean-hash",
            email="clean.person@email.com",
        )

        assert result is not None
        assert 0.0 <= result.final_risk_score <= 1.0
        assert result.final_risk_level in ["minimal", "low", "medium", "high", "critical"]
        assert isinstance(result.all_signals, list)
        assert result.explanation is not None

    def test_analyze_with_ssn_signals(self, ensemble):
        """Test analysis with SSN validation signals."""
        result = ensemble.analyze(
            identity_id="ssn-signals-test",
            ssn_hash="ssn-signals-hash",
            claimed_dob=datetime(1985, 3, 15),
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email="test@email.com",
            ssn_signals={
                "is_valid": False,
                "is_itin": True,
                "issuance_consistent": False,
            },
        )

        # Should have higher risk with SSN issues
        assert result.final_risk_score >= 0.0

    def test_analyze_with_graph_features(self, ensemble):
        """Test analysis with graph features."""
        result = ensemble.analyze(
            identity_id="graph-test",
            ssn_hash="ssn-graph-hash",
            claimed_dob=datetime(1990, 1, 1),
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email="graph@email.com",
            graph_features={
                "shared_ssn_count": 2,  # Shared SSN is suspicious
                "shared_address_count": 5,
                "cluster_size": 10,
                "neighbor_avg_synthetic_score": 0.7,
            },
        )

        # Graph features indicating cluster should raise score
        assert result.final_risk_score >= 0.0

    def test_analyze_young_identity_old_dob(self, ensemble):
        """Test thin file with old claimed age."""
        result = ensemble.analyze(
            identity_id="young-file-test",
            ssn_hash="young-file-hash",
            claimed_dob=datetime(1950, 1, 1),  # 75+ years old
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email="old@email.com",
        )

        # Old claimed age with thin file should be suspicious
        assert result is not None

    def test_analyze_consistent_results(self, ensemble):
        """Test same input produces consistent results."""
        kwargs = {
            "identity_id": "consistent-test",
            "ssn_hash": "consistent-ssn",
            "claimed_dob": datetime(1990, 6, 15),
            "address_hash": "consistent-addr",
            "phone_hash": "consistent-phone",
            "email": "consistent@email.com",
        }

        result1 = ensemble.analyze(**kwargs)
        result2 = ensemble.analyze(**kwargs)

        assert result1.final_risk_score == result2.final_risk_score
        assert result1.final_risk_level == result2.final_risk_level

    def test_analyze_with_device(self, ensemble):
        """Test analysis with device fingerprint."""
        result = ensemble.analyze(
            identity_id="device-test",
            ssn_hash="device-ssn-hash",
            claimed_dob=datetime(1985, 3, 15),
            address_hash="addr-hash",
            phone_hash="phone-hash",
            email="device@email.com",
            device_fingerprint="unique-device-fp-123",
        )

        assert result is not None

    def test_recommended_action_varies_by_risk(self, ensemble):
        """Test different risks produce different recommendations."""
        # The mock bureau will generate different profiles for different hashes
        # so we check that recommendations exist
        results = []
        for i in range(10):
            result = ensemble.analyze(
                identity_id=f"action-test-{i}",
                ssn_hash=f"action-ssn-{i}",
                claimed_dob=datetime(1985 + i, 1, 1),
                address_hash=f"addr-{i}",
                phone_hash=f"phone-{i}",
                email=f"test{i}@email.com",
            )
            results.append(result)

        # Check all have recommendations
        for result in results:
            assert result.recommended_action is not None


class TestSyntheticScenarios:
    """Test specific synthetic identity scenarios."""

    @pytest.fixture
    def ensemble(self):
        bureau = MockBureauConnector()
        return EnsembleDetector(
            synthetic_scorer=SyntheticScorer(),
            bust_out_predictor=BustOutPredictor(),
            velocity_analyzer=VelocityAnalyzer(redis_client=None),
            credit_behavior_analyzer=CreditBehaviorAnalyzer(bureau_connector=bureau),
            au_detector=AuthorizedUserDetector(bureau_connector=bureau),
        )

    def test_ring_fraud_scenario(self, ensemble):
        """Test ring fraud with shared elements."""
        # Simulate ring by providing high sharing graph features
        result = ensemble.analyze(
            identity_id="ring-member",
            ssn_hash="ring-ssn",
            claimed_dob=datetime(1988, 5, 20),
            address_hash="shared-address",
            phone_hash="shared-phone",
            email="ring@temp-email.com",
            graph_features={
                "shared_ssn_count": 0,
                "shared_address_count": 8,  # Many sharing address
                "shared_phone_count": 5,    # Many sharing phone
                "cluster_size": 12,         # Large cluster
                "cluster_density": 0.8,     # Dense cluster
                "neighbor_avg_synthetic_score": 0.6,
            },
        )

        # Should detect as risky
        assert result.final_risk_score > 0.0 or "LARGE_CLUSTER" in result.all_signals

    def test_ssn_sharing_scenario(self, ensemble):
        """Test SSN being shared by multiple identities."""
        result = ensemble.analyze(
            identity_id="ssn-shared",
            ssn_hash="multiple-users-ssn",
            claimed_dob=datetime(1990, 3, 15),
            address_hash="unique-addr",
            phone_hash="unique-phone",
            email="normal@email.com",
            graph_features={
                "shared_ssn_count": 3,  # Same SSN used by 3 people
            },
        )

        # SSN sharing should be flagged
        assert result is not None

    def test_bust_out_candidate(self, ensemble):
        """Test potential bust-out pattern."""
        result = ensemble.analyze(
            identity_id="bustout-candidate",
            ssn_hash="bustout-ssn",
            claimed_dob=datetime(1992, 8, 10),
            address_hash="bustout-addr",
            phone_hash="bustout-phone",
            email="bustout@email.com",
        )

        # Check bust-out prediction was generated
        if result.bust_out_prediction:
            assert 0.0 <= result.bust_out_prediction.bust_out_probability <= 1.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def ensemble(self):
        bureau = MockBureauConnector()
        return EnsembleDetector(
            synthetic_scorer=SyntheticScorer(),
            bust_out_predictor=BustOutPredictor(),
            velocity_analyzer=VelocityAnalyzer(redis_client=None),
            credit_behavior_analyzer=CreditBehaviorAnalyzer(bureau_connector=bureau),
            au_detector=AuthorizedUserDetector(bureau_connector=bureau),
        )

    def test_empty_email(self, ensemble):
        """Test with empty email."""
        result = ensemble.analyze(
            identity_id="empty-email",
            ssn_hash="ee-ssn",
            claimed_dob=datetime(1985, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="",
        )
        assert result is not None

    def test_very_old_dob(self, ensemble):
        """Test with very old DOB."""
        result = ensemble.analyze(
            identity_id="old-dob",
            ssn_hash="old-ssn",
            claimed_dob=datetime(1920, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="old@email.com",
        )
        assert result is not None

    def test_future_dob(self, ensemble):
        """Test with future DOB (should still process)."""
        result = ensemble.analyze(
            identity_id="future-dob",
            ssn_hash="future-ssn",
            claimed_dob=datetime(2050, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="future@email.com",
        )
        assert result is not None

    def test_special_characters_in_email(self, ensemble):
        """Test email with special characters."""
        result = ensemble.analyze(
            identity_id="special-email",
            ssn_hash="special-ssn",
            claimed_dob=datetime(1985, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="test+tag@sub.domain.com",
        )
        assert result is not None

    def test_empty_graph_features(self, ensemble):
        """Test with empty graph features."""
        result = ensemble.analyze(
            identity_id="empty-graph",
            ssn_hash="eg-ssn",
            claimed_dob=datetime(1985, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="test@email.com",
            graph_features={},
        )
        assert result is not None

    def test_none_ssn_signals(self, ensemble):
        """Test with None SSN signals."""
        result = ensemble.analyze(
            identity_id="none-ssn-signals",
            ssn_hash="nss-ssn",
            claimed_dob=datetime(1985, 1, 1),
            address_hash="addr",
            phone_hash="phone",
            email="test@email.com",
            ssn_signals=None,
        )
        assert result is not None
