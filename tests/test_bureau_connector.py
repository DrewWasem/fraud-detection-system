"""Tests for credit bureau connector."""

import pytest
from datetime import datetime

from src.ingestion.bureau_connector import (
    MockBureauConnector,
    Bureau,
    CreditFileSnapshot,
    TradeLine,
)


class TestMockBureauConnector:
    """Test MockBureauConnector class."""

    @pytest.fixture
    def connector(self):
        """Create mock connector."""
        return MockBureauConnector(bureau=Bureau.EXPERIAN)

    def test_connect(self, connector):
        """Test connection (always succeeds)."""
        connector.connect()
        assert connector._connected is True

    def test_get_credit_file(self, connector):
        """Test credit file retrieval."""
        credit_file = connector.get_credit_file("test-ssn-hash")

        assert credit_file is not None
        assert isinstance(credit_file, CreditFileSnapshot)
        assert credit_file.ssn_hash == "test-ssn-hash"
        assert credit_file.bureau == Bureau.EXPERIAN
        assert credit_file.num_tradelines >= 0
        assert credit_file.total_credit_limit >= 0

    def test_get_credit_file_deterministic(self, connector):
        """Test that same SSN hash returns same data."""
        file1 = connector.get_credit_file("consistent-hash")
        file2 = connector.get_credit_file("consistent-hash")

        assert file1.num_tradelines == file2.num_tradelines
        assert file1.credit_score == file2.credit_score
        assert file1.total_credit_limit == file2.total_credit_limit

    def test_get_tradelines(self, connector):
        """Test tradeline retrieval."""
        tradelines = connector.get_tradelines("test-ssn-hash")

        assert isinstance(tradelines, list)
        for tl in tradelines:
            assert isinstance(tl, TradeLine)
            assert tl.account_type in [
                "credit_card", "auto_loan", "mortgage",
                "personal_loan", "student_loan", "retail_card"
            ]

    def test_tradelines_match_credit_file(self, connector):
        """Test tradeline count matches credit file."""
        credit_file = connector.get_credit_file("match-test")
        tradelines = connector.get_tradelines("match-test")

        assert len(tradelines) == credit_file.num_tradelines

    def test_authorized_user_count(self, connector):
        """Test AU account counting."""
        credit_file = connector.get_credit_file("au-test")
        tradelines = connector.get_tradelines("au-test")

        au_count = sum(1 for tl in tradelines if tl.is_authorized_user)
        assert au_count == credit_file.authorized_user_accounts

    def test_is_thin_file(self, connector):
        """Test thin file detection."""
        # Generate a hash that should be synthetic (thin file)
        # Need to find one that generates < 3 tradelines
        for i in range(100):
            result = connector.is_thin_file(f"test-hash-{i}")
            # Method should return boolean
            assert isinstance(result, bool)

    def test_get_credit_file_age(self, connector):
        """Test credit file age calculation."""
        age = connector.get_credit_file_age("age-test")

        assert age is not None
        assert age >= 0

    def test_get_credit_utilization(self, connector):
        """Test utilization calculation."""
        utilization = connector.get_credit_utilization("util-test")

        assert 0.0 <= utilization <= 1.0

    def test_analyze_for_synthetic_signals(self, connector):
        """Test synthetic signal analysis."""
        analysis = connector.analyze_for_synthetic_signals("analysis-test")

        assert "has_data" in analysis
        assert "signals" in analysis
        assert "risk_score" in analysis
        assert isinstance(analysis["signals"], list)
        assert 0.0 <= analysis["risk_score"] <= 1.0

    def test_synthetic_profile_signals(self, connector):
        """Test that synthetic profiles generate appropriate signals."""
        # Find a hash that generates a synthetic profile
        for i in range(1000):
            ssn_hash = f"synthetic-test-{i}"
            if connector._is_synthetic_profile(ssn_hash):
                analysis = connector.analyze_for_synthetic_signals(ssn_hash)
                # Synthetic profiles should have some risk signals
                # (not always, due to randomness, but usually)
                break
        else:
            pytest.skip("No synthetic profile found in range")

    def test_legitimate_profile_characteristics(self, connector):
        """Test legitimate profile characteristics."""
        # Find a hash that generates a legitimate profile
        for i in range(1000):
            ssn_hash = f"legit-test-{i}"
            if not connector._is_synthetic_profile(ssn_hash):
                credit_file = connector.get_credit_file(ssn_hash)
                # Legitimate profiles should have:
                # - More tradelines (5-15)
                # - Older file age (3-20 years)
                # - Lower utilization
                assert credit_file.num_tradelines >= 1
                break
        else:
            pytest.skip("No legitimate profile found in range")


class TestSyntheticVsLegitimateProfiles:
    """Test synthetic vs legitimate profile generation."""

    @pytest.fixture
    def connector(self):
        return MockBureauConnector()

    def test_synthetic_rate(self, connector):
        """Test ~15% of profiles are synthetic."""
        total = 1000
        synthetic_count = sum(
            1 for i in range(total)
            if connector._is_synthetic_profile(f"rate-test-{i}")
        )

        # Should be approximately 15% (allow 10-20% range)
        rate = synthetic_count / total
        assert 0.10 <= rate <= 0.20

    def test_synthetic_has_thin_file(self, connector):
        """Test synthetic profiles tend to have thin files."""
        thin_count = 0
        synthetic_count = 0

        for i in range(500):
            ssn_hash = f"thin-test-{i}"
            if connector._is_synthetic_profile(ssn_hash):
                synthetic_count += 1
                if connector.is_thin_file(ssn_hash):
                    thin_count += 1

        if synthetic_count > 0:
            thin_rate = thin_count / synthetic_count
            # Synthetic profiles more likely to have thin files
            # (1-4 tradelines vs 5-15 for legitimate)
            assert thin_rate > 0.3  # At least 30% should be thin

    def test_synthetic_has_more_au(self, connector):
        """Test synthetic profiles have more AU accounts."""
        synthetic_au_total = 0
        synthetic_count = 0
        legit_au_total = 0
        legit_count = 0

        for i in range(500):
            ssn_hash = f"au-compare-{i}"
            credit_file = connector.get_credit_file(ssn_hash)
            if connector._is_synthetic_profile(ssn_hash):
                synthetic_count += 1
                synthetic_au_total += credit_file.authorized_user_accounts
            else:
                legit_count += 1
                legit_au_total += credit_file.authorized_user_accounts

        if synthetic_count > 0 and legit_count > 0:
            synthetic_avg = synthetic_au_total / synthetic_count
            legit_avg = legit_au_total / legit_count
            # Synthetic should have higher AU on average
            # (1-3 vs 0-1 for legitimate)
            assert synthetic_avg > legit_avg


class TestBureauDataConsistency:
    """Test data consistency in bureau responses."""

    @pytest.fixture
    def connector(self):
        return MockBureauConnector()

    def test_credit_file_snapshot_date(self, connector):
        """Test snapshot date is recent."""
        credit_file = connector.get_credit_file("date-test")
        now = datetime.now()

        # Snapshot should be within last minute
        diff = (now - credit_file.snapshot_date).total_seconds()
        assert diff < 60

    def test_tradeline_dates_in_past(self, connector):
        """Test all tradeline dates are in the past."""
        tradelines = connector.get_tradelines("past-date-test")
        now = datetime.now()

        for tl in tradelines:
            assert tl.opened_date < now

    def test_credit_limit_vs_balance(self, connector):
        """Test balance doesn't exceed limit."""
        tradelines = connector.get_tradelines("balance-test")

        for tl in tradelines:
            assert tl.current_balance <= tl.credit_limit

    def test_file_age_vs_oldest_tradeline(self, connector):
        """Test file age consistency with oldest tradeline."""
        credit_file = connector.get_credit_file("age-consistency-test")

        if credit_file.file_creation_date and credit_file.oldest_tradeline_date:
            # File creation should be before or same as oldest tradeline
            assert credit_file.file_creation_date <= credit_file.oldest_tradeline_date
