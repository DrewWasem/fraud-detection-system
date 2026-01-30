"""Graph API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api import dependencies

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/identity/{identity_id}")
async def get_identity_graph(
    identity_id: str,
    depth: int = Query(default=2, ge=1, le=5),
):
    """
    Get identity subgraph for investigation.

    Returns the network of nodes and edges around the specified identity,
    including shared PII elements and connected identities.
    """
    try:
        identity_graph = dependencies.get_identity_graph()
        result = identity_graph.get_identity_graph(identity_id, depth=depth)

        return {
            "identity_id": identity_id,
            "nodes": result.get("nodes", []),
            "edges": result.get("edges", []),
            "metadata": {
                "depth": depth,
                "node_count": len(result.get("nodes", [])),
                "edge_count": len(result.get("edges", [])),
            },
        }

    except Exception as e:
        logger.error(f"Error getting identity graph: {e}")
        return {
            "identity_id": identity_id,
            "nodes": [],
            "edges": [],
            "metadata": {"depth": depth, "error": str(e)},
        }


@router.get("/cluster/{cluster_id}")
async def get_cluster(cluster_id: str):
    """
    Get synthetic cluster details.

    Returns information about a detected synthetic identity cluster,
    including member identities and shared elements.
    """
    try:
        cluster_detector = dependencies.get_cluster_detector()
        members = cluster_detector.get_cluster_members(cluster_id)

        if not members:
            return {
                "cluster_id": cluster_id,
                "member_count": 0,
                "members": [],
                "cluster_score": 0.0,
                "risk_level": "unknown",
                "message": "Cluster not found or empty",
            }

        # Get cluster metrics
        # In a full implementation, we'd store cluster metadata
        return {
            "cluster_id": cluster_id,
            "member_count": len(members),
            "members": members[:100],  # Limit response size
            "cluster_score": 0.0,  # Would be stored/calculated
            "risk_level": "medium" if len(members) >= 5 else "low",
        }

    except Exception as e:
        logger.error(f"Error getting cluster: {e}")
        return {
            "cluster_id": cluster_id,
            "member_count": 0,
            "members": [],
            "cluster_score": 0.0,
            "risk_level": "unknown",
            "error": str(e),
        }


@router.get("/cluster/{cluster_id}/members")
async def get_cluster_members(cluster_id: str):
    """Get members of a synthetic cluster."""
    try:
        cluster_detector = dependencies.get_cluster_detector()
        members = cluster_detector.get_cluster_members(cluster_id)

        return {
            "cluster_id": cluster_id,
            "members": members,
            "count": len(members),
        }

    except Exception as e:
        logger.error(f"Error getting cluster members: {e}")
        return {
            "cluster_id": cluster_id,
            "members": [],
            "count": 0,
            "error": str(e),
        }


@router.get("/clusters")
async def list_clusters(
    min_size: int = Query(default=3, ge=2),
    risk_level: Optional[str] = None,
):
    """
    List detected synthetic clusters.

    Runs cluster detection on the identity graph and returns
    clusters meeting the specified criteria.
    """
    try:
        cluster_detector = dependencies.get_cluster_detector()
        clusters = cluster_detector.detect_clusters(min_size=min_size)

        # Filter by risk level if specified
        if risk_level:
            clusters = [c for c in clusters if c.risk_level == risk_level]

        # Convert to response format
        cluster_data = [
            {
                "cluster_id": c.cluster_id,
                "member_count": c.member_count,
                "cluster_score": c.cluster_score,
                "risk_level": c.risk_level,
                "center_identity": c.center_identity,
                "shared_elements": c.shared_elements,
            }
            for c in clusters
        ]

        return {
            "clusters": cluster_data,
            "total_count": len(cluster_data),
            "filters": {
                "min_size": min_size,
                "risk_level": risk_level,
            },
        }

    except Exception as e:
        logger.error(f"Error listing clusters: {e}")
        return {
            "clusters": [],
            "total_count": 0,
            "error": str(e),
        }


@router.get("/shared-elements/{identity_id}")
async def get_shared_elements(identity_id: str):
    """
    Get identities sharing elements with given identity.

    Returns lists of other identities that share SSN, address,
    phone, email, or device with the specified identity.
    """
    try:
        identity_graph = dependencies.get_identity_graph()
        shared = identity_graph.find_shared_elements(identity_id)

        # Calculate risk based on sharing
        risk_indicators = []
        if shared.get("shared_ssn"):
            risk_indicators.append("SHARED_SSN")
        if len(shared.get("shared_phone", [])) > 2:
            risk_indicators.append("HIGH_PHONE_SHARING")
        if len(shared.get("shared_address", [])) > 5:
            risk_indicators.append("HIGH_ADDRESS_SHARING")

        return {
            "identity_id": identity_id,
            "shared_ssn": shared.get("shared_ssn", []),
            "shared_address": shared.get("shared_address", []),
            "shared_phone": shared.get("shared_phone", []),
            "shared_email": shared.get("shared_email", []),
            "shared_device": shared.get("shared_device", []),
            "risk_indicators": risk_indicators,
            "total_connections": sum(
                len(v) for v in shared.values() if isinstance(v, list)
            ),
        }

    except Exception as e:
        logger.error(f"Error getting shared elements: {e}")
        return {
            "identity_id": identity_id,
            "shared_ssn": [],
            "shared_address": [],
            "shared_phone": [],
            "shared_email": [],
            "shared_device": [],
            "risk_indicators": [],
            "total_connections": 0,
            "error": str(e),
        }


@router.get("/features/{identity_id}")
async def get_graph_features(identity_id: str):
    """
    Get graph-based features for an identity.

    Returns computed graph metrics used for synthetic identity detection.
    """
    try:
        graph_extractor = dependencies.get_graph_feature_extractor()
        features = graph_extractor.extract_features(identity_id)

        return {
            "identity_id": identity_id,
            "features": {
                "degree": features.degree,
                "weighted_degree": features.weighted_degree,
                "clustering_coefficient": features.clustering_coefficient,
                "betweenness_centrality": features.betweenness_centrality,
                "pagerank": features.pagerank,
                "shared_ssn_count": features.shared_ssn_count,
                "shared_address_count": features.shared_address_count,
                "shared_phone_count": features.shared_phone_count,
                "shared_device_count": features.shared_device_count,
                "cluster_size": features.cluster_size,
                "cluster_density": features.cluster_density,
                "neighbor_avg_synthetic_score": features.neighbor_avg_synthetic_score,
            },
            "feature_vector": features.feature_vector.tolist(),
        }

    except Exception as e:
        logger.error(f"Error getting graph features: {e}")
        return {
            "identity_id": identity_id,
            "features": {},
            "feature_vector": [],
            "error": str(e),
        }


@router.post("/detect-clusters")
async def run_cluster_detection(
    min_size: int = Query(default=3, ge=2),
    algorithm: str = Query(default="louvain", pattern="^(louvain|label_propagation)$"),
):
    """
    Run cluster detection on the identity graph.

    This endpoint triggers a fresh cluster detection run using
    the specified algorithm.
    """
    try:
        cluster_detector = dependencies.get_cluster_detector()
        clusters = cluster_detector.detect_clusters(
            min_size=min_size,
            algorithm=algorithm,
        )

        # Update cluster assignments in the graph
        identity_graph = dependencies.get_identity_graph()
        for cluster in clusters:
            for member_id in cluster.member_identities:
                try:
                    identity_graph.assign_cluster(member_id, cluster.cluster_id)
                except Exception as e:
                    logger.warning(f"Failed to assign cluster for {member_id}: {e}")

        return {
            "status": "completed",
            "algorithm": algorithm,
            "min_size": min_size,
            "clusters_found": len(clusters),
            "clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "member_count": c.member_count,
                    "cluster_score": c.cluster_score,
                    "risk_level": c.risk_level,
                }
                for c in clusters[:50]  # Limit response
            ],
        }

    except Exception as e:
        logger.error(f"Error running cluster detection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cluster detection failed: {str(e)}",
        )
