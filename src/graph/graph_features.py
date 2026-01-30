"""Extract graph-based features for ML models."""

import logging
from dataclasses import dataclass
from typing import Optional

import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GraphFeatures:
    """Graph-based features for an identity."""

    identity_id: str
    degree: int
    weighted_degree: float
    clustering_coefficient: float
    betweenness_centrality: float
    pagerank: float
    shared_ssn_count: int
    shared_address_count: int
    shared_phone_count: int
    shared_email_count: int
    shared_device_count: int
    cluster_id: Optional[str]
    cluster_size: int
    cluster_density: float
    neighbor_avg_synthetic_score: float
    neighbor_max_synthetic_score: float
    high_risk_neighbor_count: int
    feature_vector: np.ndarray


class GraphFeatureExtractor:
    """Extracts graph-based features for synthetic identity detection."""

    def __init__(self, graph_driver=None):
        """
        Initialize feature extractor.

        Args:
            graph_driver: Neo4j driver instance
        """
        self._driver = graph_driver
        self._cached_graph: Optional[nx.Graph] = None
        self._cached_metrics: dict = {}

    def build_graph(self) -> nx.Graph:
        """Build networkx graph from Neo4j."""
        if self._cached_graph is not None:
            return self._cached_graph

        G = nx.Graph()

        if not self._driver:
            return G

        with self._driver.session() as session:
            # Get all identity relationships
            query = """
            MATCH (i1:Identity)-[r]->(elem)<-[r2]-(i2:Identity)
            WHERE i1 <> i2 AND type(r) IN ['HAS_SSN', 'HAS_ADDRESS', 'HAS_PHONE', 'HAS_EMAIL', 'USES_DEVICE']
            RETURN i1.identity_id as id1, i2.identity_id as id2,
                   type(r) as rel_type, i1.synthetic_score as score1, i2.synthetic_score as score2
            """

            result = session.run(query)
            for record in result:
                G.add_node(
                    record["id1"],
                    synthetic_score=record["score1"] or 0.0,
                )
                G.add_node(
                    record["id2"],
                    synthetic_score=record["score2"] or 0.0,
                )

                # Add or update edge
                if G.has_edge(record["id1"], record["id2"]):
                    G[record["id1"]][record["id2"]]["rel_types"].add(
                        record["rel_type"]
                    )
                else:
                    G.add_edge(
                        record["id1"],
                        record["id2"],
                        rel_types={record["rel_type"]},
                    )

        self._cached_graph = G
        return G

    def compute_global_metrics(self, G: nx.Graph) -> None:
        """Pre-compute expensive global metrics."""
        if "pagerank" not in self._cached_metrics:
            self._cached_metrics["pagerank"] = nx.pagerank(G)

        if "betweenness" not in self._cached_metrics:
            # Sample for large graphs
            if len(G.nodes()) > 10000:
                self._cached_metrics["betweenness"] = nx.betweenness_centrality(
                    G, k=min(500, len(G.nodes()))
                )
            else:
                self._cached_metrics["betweenness"] = nx.betweenness_centrality(G)

    def extract_features(self, identity_id: str) -> GraphFeatures:
        """
        Extract graph features for an identity.

        Args:
            identity_id: Identity to extract features for

        Returns:
            GraphFeatures with all computed features
        """
        G = self.build_graph()

        if identity_id not in G:
            return self._empty_features(identity_id)

        self.compute_global_metrics(G)

        # Basic degree metrics
        degree = G.degree(identity_id)
        weighted_degree = sum(
            len(G[identity_id][n].get("rel_types", set()))
            for n in G.neighbors(identity_id)
        )

        # Clustering coefficient
        clustering = nx.clustering(G, identity_id)

        # Centrality metrics
        betweenness = self._cached_metrics["betweenness"].get(identity_id, 0.0)
        pagerank = self._cached_metrics["pagerank"].get(identity_id, 0.0)

        # Shared element counts
        shared_counts = self._count_shared_elements(G, identity_id)

        # Cluster metrics
        cluster_size, cluster_density = self._get_cluster_metrics(G, identity_id)

        # Neighbor synthetic scores
        neighbor_scores = [
            G.nodes[n].get("synthetic_score", 0.0) for n in G.neighbors(identity_id)
        ]
        avg_neighbor_score = (
            np.mean(neighbor_scores) if neighbor_scores else 0.0
        )
        max_neighbor_score = (
            np.max(neighbor_scores) if neighbor_scores else 0.0
        )
        high_risk_count = sum(1 for s in neighbor_scores if s > 0.5)

        # Get cluster ID from node if available
        cluster_id = G.nodes[identity_id].get("cluster_id")

        # Build feature vector
        feature_vector = np.array(
            [
                degree,
                weighted_degree,
                clustering,
                betweenness,
                pagerank,
                shared_counts["ssn"],
                shared_counts["address"],
                shared_counts["phone"],
                shared_counts["email"],
                shared_counts["device"],
                cluster_size,
                cluster_density,
                avg_neighbor_score,
                max_neighbor_score,
                high_risk_count,
            ]
        )

        return GraphFeatures(
            identity_id=identity_id,
            degree=degree,
            weighted_degree=weighted_degree,
            clustering_coefficient=clustering,
            betweenness_centrality=betweenness,
            pagerank=pagerank,
            shared_ssn_count=shared_counts["ssn"],
            shared_address_count=shared_counts["address"],
            shared_phone_count=shared_counts["phone"],
            shared_email_count=shared_counts["email"],
            shared_device_count=shared_counts["device"],
            cluster_id=cluster_id,
            cluster_size=cluster_size,
            cluster_density=cluster_density,
            neighbor_avg_synthetic_score=avg_neighbor_score,
            neighbor_max_synthetic_score=max_neighbor_score,
            high_risk_neighbor_count=high_risk_count,
            feature_vector=feature_vector,
        )

    def _count_shared_elements(self, G: nx.Graph, identity_id: str) -> dict:
        """Count shared elements by type."""
        counts = {"ssn": 0, "address": 0, "phone": 0, "device": 0, "email": 0}

        type_mapping = {
            "HAS_SSN": "ssn",
            "HAS_ADDRESS": "address",
            "HAS_PHONE": "phone",
            "HAS_EMAIL": "email",
            "USES_DEVICE": "device",
        }

        for neighbor in G.neighbors(identity_id):
            rel_types = G[identity_id][neighbor].get("rel_types", set())
            for rel_type in rel_types:
                element_type = type_mapping.get(rel_type)
                if element_type:
                    counts[element_type] += 1

        return counts

    def _get_cluster_metrics(
        self, G: nx.Graph, identity_id: str
    ) -> tuple[int, float]:
        """Get cluster size and density for identity's cluster."""
        # Get connected component
        component = nx.node_connected_component(G, identity_id)
        subgraph = G.subgraph(component)

        cluster_size = len(component)
        cluster_density = nx.density(subgraph)

        return cluster_size, cluster_density

    def _empty_features(self, identity_id: str) -> GraphFeatures:
        """Return empty features for identity not in graph."""
        return GraphFeatures(
            identity_id=identity_id,
            degree=0,
            weighted_degree=0.0,
            clustering_coefficient=0.0,
            betweenness_centrality=0.0,
            pagerank=0.0,
            shared_ssn_count=0,
            shared_address_count=0,
            shared_phone_count=0,
            shared_email_count=0,
            shared_device_count=0,
            cluster_id=None,
            cluster_size=1,
            cluster_density=0.0,
            neighbor_avg_synthetic_score=0.0,
            neighbor_max_synthetic_score=0.0,
            high_risk_neighbor_count=0,
            feature_vector=np.zeros(15),
        )

    def extract_batch(self, identity_ids: list[str]) -> list[GraphFeatures]:
        """Extract features for multiple identities."""
        return [self.extract_features(id) for id in identity_ids]
