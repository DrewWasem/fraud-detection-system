"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health(self, client):
        """Test detailed health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data


class TestScoringEndpoints:
    """Test scoring API endpoints."""

    def test_score_synthetic(self, client):
        """Test synthetic scoring endpoint."""
        payload = {
            "ssn_last4": "1234",
            "ssn_first5": "12345",
            "dob": "1985-03-15",
            "first_name": "John",
            "last_name": "Smith",
            "address": {
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip": "90210"
            },
            "phone": "555-123-4567",
            "email": "john.smith@email.com",
            "application_date": "2024-01-15"
        }

        response = client.post("/api/v1/score/synthetic", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "risk_level" in data

    def test_score_bust_out(self, client):
        """Test bust-out scoring endpoint."""
        payload = {
            "account_id": "acct_123",
            "include_credit_behavior": True
        }

        response = client.post("/api/v1/score/bust-out", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "probability" in data
        assert "risk_level" in data


class TestGraphEndpoints:
    """Test graph API endpoints."""

    def test_get_identity_graph(self, client):
        """Test identity graph endpoint."""
        response = client.get("/api/v1/graph/identity/test-id-123")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_list_clusters(self, client):
        """Test cluster listing endpoint."""
        response = client.get("/api/v1/graph/clusters")
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data


class TestInvestigationEndpoints:
    """Test investigation API endpoints."""

    def test_list_cases(self, client):
        """Test case listing endpoint."""
        response = client.get("/api/v1/investigation/cases")
        assert response.status_code == 200
        data = response.json()
        assert "cases" in data

    def test_create_case(self, client):
        """Test case creation endpoint."""
        payload = {
            "identity_id": "test-identity-123"
        }

        response = client.post("/api/v1/investigation/cases", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "case_id" in data
