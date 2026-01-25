"""Device fingerprinting for fraud detection."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device types."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    BOT = "bot"
    UNKNOWN = "unknown"


@dataclass
class DeviceFingerprint:
    """Device fingerprint data."""

    fingerprint_id: str
    device_type: DeviceType
    os: str
    os_version: str
    browser: str
    browser_version: str
    screen_resolution: Optional[str]
    timezone: Optional[str]
    language: str
    is_incognito: bool
    has_plugins: bool
    canvas_hash: Optional[str]
    webgl_hash: Optional[str]
    audio_hash: Optional[str]
    fonts_hash: Optional[str]
    is_emulator: bool
    is_vm: bool
    ip_address: str
    first_seen: datetime
    last_seen: datetime


@dataclass
class DeviceRisk:
    """Device risk assessment."""

    fingerprint_id: str
    risk_score: float
    risk_factors: list[str]
    is_known_fraud_device: bool
    associated_identity_count: int
    is_suspicious: bool


class DeviceFingerprinter:
    """Creates and analyzes device fingerprints."""

    def __init__(self, redis_client=None):
        """
        Initialize fingerprinter.

        Args:
            redis_client: Redis for fingerprint storage
        """
        self._redis = redis_client
        self._fraud_devices: set[str] = set()

    def create_fingerprint(
        self,
        user_agent: str,
        ip_address: str,
        screen_resolution: Optional[str] = None,
        timezone: Optional[str] = None,
        language: str = "en-US",
        canvas_hash: Optional[str] = None,
        webgl_hash: Optional[str] = None,
        audio_hash: Optional[str] = None,
        plugins: Optional[list[str]] = None,
    ) -> DeviceFingerprint:
        """
        Create device fingerprint from browser attributes.

        Args:
            user_agent: Browser user agent string
            ip_address: Client IP address
            screen_resolution: Screen dimensions
            timezone: Browser timezone
            language: Browser language
            canvas_hash: Canvas fingerprint hash
            webgl_hash: WebGL fingerprint hash
            audio_hash: Audio context fingerprint hash
            plugins: List of browser plugins

        Returns:
            DeviceFingerprint
        """
        # Parse user agent
        device_type, os, os_version, browser, browser_version = self._parse_user_agent(
            user_agent
        )

        # Generate fingerprint ID
        fingerprint_id = self._generate_fingerprint_id(
            user_agent,
            screen_resolution,
            timezone,
            canvas_hash,
            webgl_hash,
        )

        now = datetime.now()

        return DeviceFingerprint(
            fingerprint_id=fingerprint_id,
            device_type=device_type,
            os=os,
            os_version=os_version,
            browser=browser,
            browser_version=browser_version,
            screen_resolution=screen_resolution,
            timezone=timezone,
            language=language,
            is_incognito=self._detect_incognito(plugins),
            has_plugins=bool(plugins),
            canvas_hash=canvas_hash,
            webgl_hash=webgl_hash,
            audio_hash=audio_hash,
            fonts_hash=None,
            is_emulator=self._detect_emulator(user_agent),
            is_vm=False,  # TODO: Implement VM detection
            ip_address=ip_address,
            first_seen=now,
            last_seen=now,
        )

    def _parse_user_agent(
        self, user_agent: str
    ) -> tuple[DeviceType, str, str, str, str]:
        """Parse user agent string."""
        ua_lower = user_agent.lower()

        # Detect device type
        if "mobile" in ua_lower or "android" in ua_lower and "mobile" in ua_lower:
            device_type = DeviceType.MOBILE
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device_type = DeviceType.TABLET
        elif "bot" in ua_lower or "crawler" in ua_lower or "spider" in ua_lower:
            device_type = DeviceType.BOT
        else:
            device_type = DeviceType.DESKTOP

        # Detect OS
        if "windows" in ua_lower:
            os = "Windows"
            os_version = "Unknown"
        elif "mac os" in ua_lower or "macos" in ua_lower:
            os = "macOS"
            os_version = "Unknown"
        elif "linux" in ua_lower:
            os = "Linux"
            os_version = "Unknown"
        elif "android" in ua_lower:
            os = "Android"
            os_version = "Unknown"
        elif "ios" in ua_lower or "iphone" in ua_lower or "ipad" in ua_lower:
            os = "iOS"
            os_version = "Unknown"
        else:
            os = "Unknown"
            os_version = "Unknown"

        # Detect browser
        if "chrome" in ua_lower and "edg" not in ua_lower:
            browser = "Chrome"
        elif "firefox" in ua_lower:
            browser = "Firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            browser = "Safari"
        elif "edg" in ua_lower:
            browser = "Edge"
        else:
            browser = "Unknown"

        return device_type, os, os_version, browser, "Unknown"

    def _generate_fingerprint_id(
        self,
        user_agent: str,
        screen_resolution: Optional[str],
        timezone: Optional[str],
        canvas_hash: Optional[str],
        webgl_hash: Optional[str],
    ) -> str:
        """Generate unique fingerprint ID."""
        components = [
            user_agent,
            screen_resolution or "",
            timezone or "",
            canvas_hash or "",
            webgl_hash or "",
        ]
        combined = "|".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _detect_incognito(self, plugins: Optional[list[str]]) -> bool:
        """Detect if browser is in incognito/private mode."""
        # Incognito mode often has no plugins
        if plugins is None:
            return True
        return len(plugins) == 0

    def _detect_emulator(self, user_agent: str) -> bool:
        """Detect if device is an emulator."""
        emulator_indicators = [
            "android sdk",
            "emulator",
            "simulator",
            "genymotion",
            "bluestacks",
        ]
        ua_lower = user_agent.lower()
        return any(indicator in ua_lower for indicator in emulator_indicators)

    def assess_risk(self, fingerprint: DeviceFingerprint) -> DeviceRisk:
        """
        Assess fraud risk for a device.

        Args:
            fingerprint: Device fingerprint to assess

        Returns:
            DeviceRisk assessment
        """
        risk_factors = []
        risk_score = 0.0

        # Check if known fraud device
        is_fraud = fingerprint.fingerprint_id in self._fraud_devices
        if is_fraud:
            risk_score = 1.0
            risk_factors.append("known_fraud_device")

        # Emulators are suspicious
        if fingerprint.is_emulator:
            risk_score += 0.5
            risk_factors.append("emulator_detected")

        # Bots are very suspicious
        if fingerprint.device_type == DeviceType.BOT:
            risk_score += 0.8
            risk_factors.append("bot_detected")

        # Incognito slightly suspicious
        if fingerprint.is_incognito:
            risk_score += 0.1
            risk_factors.append("incognito_mode")

        # VMs are suspicious
        if fingerprint.is_vm:
            risk_score += 0.4
            risk_factors.append("virtual_machine")

        # Get associated identity count
        identity_count = self._get_identity_count(fingerprint.fingerprint_id)
        if identity_count > 3:
            risk_score += 0.3
            risk_factors.append(f"multiple_identities_{identity_count}")

        return DeviceRisk(
            fingerprint_id=fingerprint.fingerprint_id,
            risk_score=min(1.0, risk_score),
            risk_factors=risk_factors,
            is_known_fraud_device=is_fraud,
            associated_identity_count=identity_count,
            is_suspicious=risk_score > 0.5,
        )

    def _get_identity_count(self, fingerprint_id: str) -> int:
        """Get count of identities associated with device."""
        # TODO: Implement Redis lookup
        return 0

    def mark_fraud_device(self, fingerprint_id: str) -> None:
        """Mark a device as known fraud."""
        self._fraud_devices.add(fingerprint_id)
        # TODO: Persist to Redis/database
