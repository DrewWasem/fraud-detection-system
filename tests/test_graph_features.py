"""Tests for graph feature extraction."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.graph.graph_features import GraphFeatureExtractor, GraphFeatures


class TestGraphFeatureExtractor:
    """Test GraphFeatureExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create extractor without Neo4j."""
        return GraphFeatureExtractor(graph_driver=None)

    def test_extract_features_no_driver(self, extractor):
        """Test extraction returns empty features without driver."""
        features = extractor.extract_features("test-id")

        assert isinstance(features, GraphFeatures)
        assert features.identity_id == "test-id"
        assert features.degree == 0
        assert features.shared_ssn_count == 0
        assert features.cluster_size == 1
        assert features.neighbor_avg_synthetic_score == 0.0
        assert len(features.feature_vector) == 15

    def test_empty_features_structure(self, extractor):
        """Test empty features have correct structure."""
        features = extractor._empty_features("empty-test")

        # Check all fields are present
        assert hasattr(features, "identity_id")
        assert hasattr(features, "degree")
        assert hasattr(features, "weighted_degree")
        assert hasattr(features, "clustering_coefficient")
        assert hasattr(features, "betweenness_centrality")
        assert hasattr(features, "pagerank")
        assert hasattr(features, "shared_ssn_count")
        assert hasattr(features, "shared_address_count")
        assert hasattr(features, "shared_phone_count")
        assert hasattr(features, "shared_email_count")
        assert hasattr(features, "shared_device_count")
        assert hasattr(features, "cluster_id")
        assert hasattr(features, "cluster_size")
        assert hasattr(features, "cluster_density")
        assert hasattr(features, "neighbor_avg_synthetic_score")
        assert hasattr(features, "neighbor_max_synthetic_score")
        assert hasattr(features, "high_risk_neighbor_count")
        assert hasattr(features, "feature_vector")

    def test_feature_vector_dimensions(self, extractor):
        """Test feature vector has correct dimensions."""
        features = extractor._empty_features("dim-test")

        # Feature vector should have 15 elements
        assert features.feature_vector.shape == (15,)

    def test_feature_vector_dtype(self, extractor):
        """Test feature vector has correct type."""
        features = extractor._empty_features("dtype-test")

        assert isinstance(features.feature_vector, np.ndarray)

    def test_extract_batch(self, extractor):
        """Test batch extraction."""
        ids = ["id-1", "id-2", "id-3"]
        results = extractor.extract_batch(ids)

        assert len(results) == 3
        for features in results:
            assert isinstance(features, GraphFeatures)


class TestGraphFeatureValues:
    """Test feature value ranges and consistency."""

    @pytest.fixture
    def extractor(self):
        return GraphFeatureExtractor(graph_driver=None)

    def test_clustering_coefficient_range(self, extractor):
        """Test clustering coefficient is in [0, 1]."""
        features = extractor._empty_features("cc-test")
        assert 0.0 <= features.clustering_coefficient <= 1.0

    def test_pagerank_non_negative(self, extractor):
        """Test PageRank is non-negative."""
        features = extractor._empty_features("pr-test")
        assert features.pagerank >= 0.0

    def test_cluster_size_positive(self, extractor):
        """Test cluster size is at least 1."""
        features = extractor._empty_features("cs-test")
        assert features.cluster_size >= 1

    def test_cluster_density_range(self, extractor):
        """Test cluster density is in [0, 1]."""
        features = extractor._empty_features("cd-test")
        assert 0.0 <= features.cluster_density <= 1.0

    def test_shared_counts_non_negative(self, extractor):
        """Test all shared counts are non-negative."""
        features = extractor._empty_features("sc-test")

        assert features.shared_ssn_count >= 0
        assert features.shared_address_count >= 0
        assert features.shared_phone_count >= 0
        assert features.shared_email_count >= 0
        assert features.shared_device_count >= 0


class TestGraphFeatureExtractorWithMockDriver:
    """Test with mocked Neo4j driver."""

    @pytest.fixture
    def mock_driver(self):
        """Create mock Neo4j driver."""
        mock = MagicMock()
        mock.session.return_value.__enter__ = MagicMock()
        mock.session.return_value.__exit__ = MagicMock()
        return mock

    @pytest.fixture
    def extractor_with_mock(self, mock_driver):
        """Create extractor with mock driver."""
        return GraphFeatureExtractor(graph_driver=mock_driver)

    def test_build_graph_with_empty_results(self, extractor_with_mock, mock_driver):
        """Test building graph with empty query results."""
        # Configure mock to return empty results
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []

        G = extractor_with_mock.build_graph()

        assert len(G.nodes()) == 0
        assert len(G.edges()) == 0


class TestGraphFeaturesDataclass:
    """Test GraphFeatures dataclass."""

    def test_create_graph_features(self):
        """Test creating GraphFeatures instance."""
        features = GraphFeatures(
            identity_id="test",
            degree=5,
            weighted_degree=7.5,
            clustering_coefficient=0.5,
            betweenness_centrality=0.1,
            pagerank=0.01,
            shared_ssn_count=0,
            shared_address_count=2,
            shared_phone_count=1,
            shared_email_count=0,
            shared_device_count=0,
            cluster_id="cluster-1",
            cluster_size=3,
            cluster_density=0.67,
            neighbor_avg_synthetic_score=0.3,
            neighbor_max_synthetic_score=0.5,
            high_risk_neighbor_count=1,
            feature_vector=np.zeros(15),
        )

        assert features.identity_id == "test"
        assert features.degree == 5
        assert features.cluster_id == "cluster-1"
