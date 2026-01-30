"""API dependency injection."""

import logging
from functools import lru_cache
from typing import Optional

import redis
from neo4j import GraphDatabase

from src.config import get_settings
from src.detection.velocity_analyzer import VelocityAnalyzer
from src.detection.ensemble import EnsembleDetector
from src.detection.synthetic_scorer import SyntheticScorer
from src.detection.bust_out_predictor import BustOutPredictor
from src.detection.credit_behavior import CreditBehaviorAnalyzer
from src.detection.authorized_user import AuthorizedUserDetector
from src.graph.identity_graph import IdentityGraph
from src.graph.cluster_detector import ClusterDetector
from src.graph.graph_features import GraphFeatureExtractor
from src.investigation.case_manager import CaseManager
from src.ingestion.bureau_connector import MockBureauConnector

logger = logging.getLogger(__name__)

# Global instances (lazily initialized)
_redis_client: Optional[redis.Redis] = None
_neo4j_driver = None
_identity_graph: Optional[IdentityGraph] = None
_velocity_analyzer: Optional[VelocityAnalyzer] = None
_ensemble_detector: Optional[EnsembleDetector] = None
_cluster_detector: Optional[ClusterDetector] = None
_graph_feature_extractor: Optional[GraphFeatureExtractor] = None
_case_manager: Optional[CaseManager] = None
_bureau_connector: Optional[MockBureauConnector] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance."""
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    try:
        _redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            decode_responses=False,  # Handle bytes explicitly
        )
        # Test connection
        _redis_client.ping()
        logger.info(f"Connected to Redis at {settings.redis.host}:{settings.redis.port}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}. Velocity tracking disabled.")
        return None


def get_neo4j_driver():
    """Get Neo4j driver instance."""
    global _neo4j_driver

    if _neo4j_driver is not None:
        return _neo4j_driver

    settings = get_settings()

    try:
        _neo4j_driver = GraphDatabase.driver(
            settings.neo4j.uri,
            auth=(settings.neo4j.user, settings.neo4j.password),
        )
        # Test connection
        _neo4j_driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {settings.neo4j.uri}")
        return _neo4j_driver
    except Exception as e:
        logger.warning(f"Failed to connect to Neo4j: {e}. Graph features disabled.")
        return None


def get_identity_graph() -> IdentityGraph:
    """Get IdentityGraph instance."""
    global _identity_graph

    if _identity_graph is not None:
        return _identity_graph

    settings = get_settings()
    _identity_graph = IdentityGraph(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )

    try:
        _identity_graph.connect()
    except Exception as e:
        logger.warning(f"Failed to connect IdentityGraph: {e}")

    return _identity_graph


def get_velocity_analyzer() -> VelocityAnalyzer:
    """Get VelocityAnalyzer instance with Redis client."""
    global _velocity_analyzer

    if _velocity_analyzer is not None:
        return _velocity_analyzer

    redis_client = get_redis_client()
    _velocity_analyzer = VelocityAnalyzer(redis_client=redis_client)
    return _velocity_analyzer


def get_cluster_detector() -> ClusterDetector:
    """Get ClusterDetector instance."""
    global _cluster_detector

    if _cluster_detector is not None:
        return _cluster_detector

    neo4j_driver = get_neo4j_driver()
    _cluster_detector = ClusterDetector(graph_driver=neo4j_driver)
    return _cluster_detector


def get_graph_feature_extractor() -> GraphFeatureExtractor:
    """Get GraphFeatureExtractor instance."""
    global _graph_feature_extractor

    if _graph_feature_extractor is not None:
        return _graph_feature_extractor

    neo4j_driver = get_neo4j_driver()
    _graph_feature_extractor = GraphFeatureExtractor(graph_driver=neo4j_driver)
    return _graph_feature_extractor


def get_bureau_connector() -> MockBureauConnector:
    """Get MockBureauConnector instance."""
    global _bureau_connector

    if _bureau_connector is not None:
        return _bureau_connector

    _bureau_connector = MockBureauConnector()
    return _bureau_connector


def get_case_manager() -> CaseManager:
    """Get CaseManager instance."""
    global _case_manager

    if _case_manager is not None:
        return _case_manager

    _case_manager = CaseManager()
    return _case_manager


def get_ensemble_detector() -> EnsembleDetector:
    """Get EnsembleDetector instance with all dependencies."""
    global _ensemble_detector

    if _ensemble_detector is not None:
        return _ensemble_detector

    velocity_analyzer = get_velocity_analyzer()
    bureau_connector = get_bureau_connector()

    # Create component analyzers
    synthetic_scorer = SyntheticScorer()
    bust_out_predictor = BustOutPredictor()
    credit_behavior_analyzer = CreditBehaviorAnalyzer(bureau_connector=bureau_connector)
    au_detector = AuthorizedUserDetector(bureau_connector=bureau_connector)

    _ensemble_detector = EnsembleDetector(
        synthetic_scorer=synthetic_scorer,
        bust_out_predictor=bust_out_predictor,
        velocity_analyzer=velocity_analyzer,
        credit_behavior_analyzer=credit_behavior_analyzer,
        au_detector=au_detector,
    )

    return _ensemble_detector


async def check_redis_health() -> dict:
    """Check Redis connection health."""
    try:
        client = get_redis_client()
        if client and client.ping():
            return {"status": "up", "latency_ms": 0}
        return {"status": "down", "error": "Not connected"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def check_neo4j_health() -> dict:
    """Check Neo4j connection health."""
    try:
        driver = get_neo4j_driver()
        if driver:
            driver.verify_connectivity()
            return {"status": "up"}
        return {"status": "down", "error": "Not connected"}
    except Exception as e:
        return {"status": "down", "error": str(e)}


def cleanup():
    """Cleanup connections on shutdown."""
    global _redis_client, _neo4j_driver, _identity_graph

    if _redis_client:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None

    if _neo4j_driver:
        try:
            _neo4j_driver.close()
        except Exception:
            pass
        _neo4j_driver = None

    if _identity_graph:
        try:
            _identity_graph.close()
        except Exception:
            pass
        _identity_graph = None

    logger.info("Cleaned up all connections")
