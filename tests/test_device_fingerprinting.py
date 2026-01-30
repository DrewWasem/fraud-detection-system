"""Tests for device fingerprinting and binding scorer."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.identity_elements.device.fingerprinter import (
    DeviceFingerprinter,
    DeviceFingerprint,
    DeviceRisk,
    DeviceType,
)
from src.identity_elements.device.binding_scorer import (
    DeviceBindingScorer,
    BindingStrength,
    DeviceHistory,
)


class TestDeviceFingerprinter:
    """Test DeviceFingerprinter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.fingerprinter = DeviceFingerprinter()

    def test_create_fingerprint_desktop_chrome(self):
        """Test creating fingerprint for desktop Chrome."""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        fp = self.fingerprinter.create_fingerprint(
            user_agent=user_agent,
            ip_address="192.168.1.1",
            screen_resolution="1920x1080",
            timezone="America/New_York",
        )

        assert fp.device_type == DeviceType.DESKTOP
        assert fp.os == "Windows"
        assert fp.browser == "Chrome"
        assert fp.screen_resolution == "1920x1080"
        assert len(fp.fingerprint_id) == 32

    def test_create_fingerprint_mobile(self):
        """Test creating fingerprint for mobile device."""
        user_agent = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

        fp = self.fingerprinter.create_fingerprint(
            user_agent=user_agent,
            ip_address="10.0.0.1",
        )

        assert fp.device_type == DeviceType.MOBILE
        assert fp.os == "Android"

    def test_create_fingerprint_tablet(self):
        """Test creating fingerprint for iPad."""
        user_agent = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15"

        fp = self.fingerprinter.create_fingerprint(
            user_agent=user_agent,
            ip_address="10.0.0.2",
        )

        assert fp.device_type == DeviceType.TABLET
        assert fp.os == "iOS"

    def test_detect_emulator(self):
        """Test emulator detection."""
        user_agent = "Mozilla/5.0 (Linux; Android SDK built for x86) AppleWebKit/537.36"

        fp = self.fingerprinter.create_fingerprint(
            user_agent=user_agent,
            ip_address="10.0.0.3",
        )

        assert fp.is_emulator is True

    def test_detect_incognito_no_plugins(self):
        """Test incognito detection with no plugins."""
        fp = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Chrome/120.0.0.0",
            ip_address="10.0.0.4",
            plugins=[],
        )

        assert fp.is_incognito is True

    def test_detect_incognito_with_plugins(self):
        """Test incognito detection with plugins."""
        fp = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Chrome/120.0.0.0",
            ip_address="10.0.0.5",
            plugins=["Chrome PDF Viewer", "Native Client"],
        )

        assert fp.is_incognito is False

    def test_assess_risk_clean_device(self):
        """Test risk assessment for clean device."""
        fp = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Chrome/120.0.0.0",
            ip_address="10.0.0.6",
            plugins=["Chrome PDF Viewer"],
        )

        risk = self.fingerprinter.assess_risk(fp)

        assert risk.risk_score < 0.5
        assert risk.is_suspicious is False
        assert risk.is_known_fraud_device is False

    def test_assess_risk_emulator(self):
        """Test risk assessment for emulator."""
        fp = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Android SDK Emulator",
            ip_address="10.0.0.7",
        )

        risk = self.fingerprinter.assess_risk(fp)

        assert risk.risk_score >= 0.5
        assert "emulator_detected" in risk.risk_factors

    def test_assess_risk_bot(self):
        """Test risk assessment for bot."""
        fp = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 (compatible; Googlebot/2.1)",
            ip_address="10.0.0.8",
        )

        risk = self.fingerprinter.assess_risk(fp)

        assert risk.risk_score >= 0.8
        assert "bot_detected" in risk.risk_factors

    def test_mark_fraud_device(self):
        """Test marking device as fraud."""
        self.fingerprinter.mark_fraud_device("abc123")

        # Create a fingerprint and manually set its ID
        fp = DeviceFingerprint(
            fingerprint_id="abc123",
            device_type=DeviceType.DESKTOP,
            os="Windows",
            os_version="10",
            browser="Chrome",
            browser_version="120",
            screen_resolution="1920x1080",
            timezone="UTC",
            language="en-US",
            is_incognito=False,
            has_plugins=True,
            canvas_hash=None,
            webgl_hash=None,
            audio_hash=None,
            fonts_hash=None,
            is_emulator=False,
            is_vm=False,
            ip_address="10.0.0.9",
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

        risk = self.fingerprinter.assess_risk(fp)
        assert risk.is_known_fraud_device is True
        assert risk.risk_score == 1.0

    def test_fingerprint_id_uniqueness(self):
        """Test that different attributes produce different fingerprint IDs."""
        fp1 = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Chrome/120.0.0.0",
            ip_address="10.0.0.10",
            screen_resolution="1920x1080",
        )

        fp2 = self.fingerprinter.create_fingerprint(
            user_agent="Mozilla/5.0 Chrome/120.0.0.0",
            ip_address="10.0.0.10",
            screen_resolution="1366x768",
        )

        assert fp1.fingerprint_id != fp2.fingerprint_id


class TestDeviceFingerprinterWithRedis:
    """Test DeviceFingerprinter with Redis mock."""

    def setup_method(self):
        """Set up test fixtures with Redis mock."""
        self.redis_mock = MagicMock()
        self.fingerprinter = DeviceFingerprinter(redis_client=self.redis_mock)

    def test_associate_identity(self):
        """Test associating identity with device."""
        self.fingerprinter.associate_identity("fp123", "id456")

        # Verify Redis calls
        assert self.redis_mock.sadd.called
        assert self.redis_mock.expire.called

    def test_get_identity_count(self):
        """Test getting identity count for device."""
        self.redis_mock.scard.return_value = 5

        count = self.fingerprinter._get_identity_count("fp123")

        assert count == 5

    def test_get_associated_identities(self):
        """Test getting associated identities."""
        self.redis_mock.smembers.return_value = {"id1", "id2", "id3"}

        identities = self.fingerprinter.get_associated_identities("fp123")

        assert len(identities) == 3
        assert "id1" in identities


class TestDeviceBindingScorer:
    """Test DeviceBindingScorer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = DeviceBindingScorer()

    def test_get_binding_strength_no_redis(self):
        """Test binding strength without Redis returns defaults."""
        binding = self.scorer.get_binding_strength("identity123", "device456")

        assert binding.identity_hash == "identity123"
        assert binding.device_fingerprint == "device456"
        assert binding.binding_score == 0.0
        assert binding.interaction_count == 0

    def test_get_device_history_no_redis(self):
        """Test device history without Redis returns defaults."""
        history = self.scorer.get_device_history("identity123")

        assert history.identity_hash == "identity123"
        assert history.devices == []
        assert history.primary_device is None

    def test_calculate_risk_score_no_redis(self):
        """Test risk score calculation without Redis."""
        risk = self.scorer.calculate_risk_score("identity123", "device456")

        # New device should add risk
        assert risk >= 0.3

    def test_detect_device_sharing_no_redis(self):
        """Test device sharing detection without Redis."""
        result = self.scorer.detect_device_sharing("device123")

        assert result["is_shared"] is False
        assert result["identity_count"] == 0

    def test_detect_velocity_anomaly_no_redis(self):
        """Test velocity anomaly detection without Redis."""
        result = self.scorer.detect_velocity_anomaly("identity123")

        assert result["has_anomaly"] is False
        assert result["device_count"] == 0


class TestDeviceBindingScorerWithRedis:
    """Test DeviceBindingScorer with Redis mock."""

    def setup_method(self):
        """Set up test fixtures with Redis mock."""
        self.redis_mock = MagicMock()
        self.scorer = DeviceBindingScorer(redis_client=self.redis_mock)

    def test_record_interaction(self):
        """Test recording interaction."""
        self.scorer.record_interaction("identity123", "device456")

        # Verify Redis calls
        assert self.redis_mock.zincrby.called
        assert self.redis_mock.expire.called

    def test_get_binding_strength_with_data(self):
        """Test binding strength with Redis data."""
        # Mock Redis responses
        self.redis_mock.zscore.return_value = 10.0
        self.redis_mock.zrange.return_value = [("device456", 10.0), ("device789", 5.0)]
        self.redis_mock.hgetall.return_value = {
            'first_seen': (datetime.now() - timedelta(days=30)).isoformat(),
            'last_seen': datetime.now().isoformat(),
        }

        binding = self.scorer.get_binding_strength("identity123", "device456")

        assert binding.interaction_count == 10
        assert binding.is_primary_device is True
        assert binding.days_associated >= 29
        assert binding.binding_score > 0

    def test_detect_device_sharing_shared(self):
        """Test detecting shared device."""
        self.redis_mock.zrange.return_value = ["id1", "id2", "id3", "id4", "id5"]

        result = self.scorer.detect_device_sharing("device123", min_identities=3)

        assert result["is_shared"] is True
        assert result["identity_count"] == 5
        assert result["risk_score"] >= 0.4

    def test_detect_velocity_anomaly_high_switching(self):
        """Test detecting high device switching."""
        self.redis_mock.zrange.return_value = ["d1", "d2", "d3", "d4", "d5"]
        self.redis_mock.zrangebyscore.return_value = ["timestamp1"]

        result = self.scorer.detect_velocity_anomaly("identity123", window_hours=24)

        assert result["has_anomaly"] is True
        assert result["device_count"] == 5
        assert result["anomaly_type"] == "excessive_device_switching"


class TestBindingScoreCalculation:
    """Test binding score calculation logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = DeviceBindingScorer()

    def test_high_interaction_count_increases_score(self):
        """Test that high interaction count increases binding score."""
        low_score = self.scorer._calculate_binding_score(
            interaction_count=1,
            days_associated=0,
            is_primary=False,
            other_device_count=0,
        )

        high_score = self.scorer._calculate_binding_score(
            interaction_count=20,
            days_associated=0,
            is_primary=False,
            other_device_count=0,
        )

        assert high_score > low_score

    def test_primary_device_bonus(self):
        """Test that primary device gets bonus."""
        non_primary = self.scorer._calculate_binding_score(
            interaction_count=5,
            days_associated=10,
            is_primary=False,
            other_device_count=0,
        )

        primary = self.scorer._calculate_binding_score(
            interaction_count=5,
            days_associated=10,
            is_primary=True,
            other_device_count=0,
        )

        assert primary > non_primary
        assert primary - non_primary == pytest.approx(0.2, abs=0.01)

    def test_many_devices_penalty(self):
        """Test that many other devices reduces score."""
        few_devices = self.scorer._calculate_binding_score(
            interaction_count=5,
            days_associated=10,
            is_primary=True,
            other_device_count=2,
        )

        many_devices = self.scorer._calculate_binding_score(
            interaction_count=5,
            days_associated=10,
            is_primary=True,
            other_device_count=10,
        )

        assert few_devices > many_devices
