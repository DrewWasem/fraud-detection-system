"""Signal detection module."""

from .ssn_dob_mismatch import SSNDOBMismatchSignal
from .thin_file_detector import ThinFileSignal
from .identity_age_gap import IdentityAgeGapSignal
from .application_velocity import ApplicationVelocitySignal
from .address_instability import AddressInstabilitySignal

__all__ = [
    "SSNDOBMismatchSignal",
    "ThinFileSignal",
    "IdentityAgeGapSignal",
    "ApplicationVelocitySignal",
    "AddressInstabilitySignal",
]
