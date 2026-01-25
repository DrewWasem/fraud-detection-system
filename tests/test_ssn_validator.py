"""Tests for SSN validator."""

import pytest
from src.identity_elements.ssn.validator import SSNValidator, SSNValidationResult


class TestSSNValidator:
    """Test cases for SSN validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SSNValidator()

    def test_valid_ssn(self):
        """Test valid SSN validation."""
        result = self.validator.validate("123-45-6789")
        assert result.result == SSNValidationResult.VALID
        assert result.area_number == 123
        assert result.group_number == 45
        assert result.serial_number == 6789

    def test_valid_ssn_no_dashes(self):
        """Test valid SSN without dashes."""
        result = self.validator.validate("123456789")
        assert result.result == SSNValidationResult.VALID

    def test_invalid_area_zero(self):
        """Test SSN with zero area number."""
        result = self.validator.validate("000-45-6789")
        assert result.result == SSNValidationResult.INVALID_AREA

    def test_invalid_area_666(self):
        """Test SSN with area 666."""
        result = self.validator.validate("666-45-6789")
        assert result.result == SSNValidationResult.INVALID_AREA

    def test_itin(self):
        """Test ITIN detection (900-999 area)."""
        result = self.validator.validate("900-45-6789")
        assert result.result == SSNValidationResult.ITIN

    def test_invalid_group_zero(self):
        """Test SSN with zero group number."""
        result = self.validator.validate("123-00-6789")
        assert result.result == SSNValidationResult.INVALID_GROUP

    def test_invalid_serial_zero(self):
        """Test SSN with zero serial number."""
        result = self.validator.validate("123-45-0000")
        assert result.result == SSNValidationResult.INVALID_FORMAT

    def test_invalid_format(self):
        """Test invalid SSN format."""
        result = self.validator.validate("12-345-6789")
        assert result.result == SSNValidationResult.INVALID_FORMAT

    def test_is_valid_helper(self):
        """Test is_valid helper method."""
        assert self.validator.is_valid("123-45-6789") is True
        assert self.validator.is_valid("000-45-6789") is False
