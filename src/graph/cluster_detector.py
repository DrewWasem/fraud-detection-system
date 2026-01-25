"""Synthetic identity cluster detection."""

import logging
from dataclasses import dataclass
from typing import Optional

import networkx as nx
from neo4j import GraphDatabase

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SyntheticCluster:
    """Detected synthetic identity cluster."""

    cluster_id: str
    member_count: int
    member_identities: list[str]
    shared_elements: dict  # What elements link the cluster
    cluster_score: float  # How likely synthetic (0-1)
    center_identity: str  # Most connected identity
    risk_level: str  # low, medium, high, critical


class ClusterDetector:
    """Detects clusters of potentially synthetic identities."""

    def __init__(self, graph_driver=None):
        """
        Initialize cluster detector.

        Args:
            graph_driver: Neo4j driver instance
        """
        self._driver = graph_driver
        self._settings = get_settings()

    def connect(self, uri: str, user: str, password: str) -> None:
        """Connect to Neo4j."""
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def detect_clusters(
        self,
        min_size: int = 3,
        algorithm: str = "louvain",
    ) -> list[SyntheticCluster]:
        """
        Detect synthetic identity clusters in the graph.

        Args:
            min_size: Minimum cluster size to report
            algorithm: Clustering algorithm (louvain, label_propagation)

        Returns:
            List of detected clusters
        """
        # Build networkx graph from Neo4j
        G = self._build_identity_network()

        if len(G.nodes()) == 0:
            return []

        # Run clustering
        if algorithm == "louvain":
            communities = self._louvain_clustering(G)
        elif algorithm == "label_propagation":
            communities = self._label_propagation(G)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        # Filter and analyze clusters
        clusters = []
        for i, community in enumerate(communities):
            if len(community) >= min_size:
                cluster = self._analyze_cluster(
                    G, list(community), f"cluster_{i}"
                )
                clusters.append(cluster)

        # Sort by risk
        clusters.sort(key=lambda c: c.cluster_score, reverse=True)
        return clusters

    def _build_identity_network(self) -> nx.Graph:
        """Build networkx graph from Neo4j identity graph."""
        G = nx.Graph()

        if not self._driver:
            return G

        with self._driver.session() as session:
            # Get identities sharing SSNs
            ssn_query = """
            MATCH (i1:Identity)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(i2:Identity)
            WHERE i1 <> i2
            RETURN i1.identity_id as id1, i2.identity_id as id2, 'ssn' as type
            """

            # Get identities sharing addresses
            addr_query = """
            MATCH (i1:Identity)-[:HAS_ADDRESS]->(a:Address)<-[:HAS_ADDRESS]-(i2:Identity)
            WHERE i1 <> i2
            RETURN i1.identity_id as id1, i2.identity_id as id2, 'address' as type
            """

            # Get identities sharing phones
            phone_query = """
            MATCH (i1:Identity)-[:HAS_PHONE]->(p:Phone)<-[:HAS_PHONE]-(i2:Identity)
            WHERE i1 <> i2
            RETURN i1.identity_id as id1, i2.identity_id as id2, 'phone' as type
            """

            # Get identities sharing devices
            device_query = """
            MATCH (i1:Identity)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(i2:Identity)
            WHERE i1 <> i2
            RETURN i1.identity_id as id1, i2.identity_id as id2, 'device' as type
            """

            for query in [ssn_query, addr_query, phone_query, device_query]:
                try:
                    result = session.run(query)
                    for record in result:
                        id1, id2 = record["id1"], record["id2"]
                        link_type = record["type"]

                        if G.has_edge(id1, id2):
                            # Add to existing edge
                            G[id1][id2]["shared_types"].add(link_type)
                            G[id1][id2]["weight"] += self._get_link_weight(link_type)
                        else:
                            G.add_edge(
                                id1,
                                id2,
                                shared_types={link_type},
                                weight=self._get_link_weight(link_type),
                            )
                except Exception as e:
                    logger.error(f"Query failed: {e}")

        return G

    def _get_link_weight(self, link_type: str) -> float:
        """Get weight for different link types."""
        weights = {
            "ssn": 1.0,  # SSN sharing is very suspicious
            "phone": 0.6,
            "address": 0.4,
            "device": 0.7,
            "email": 0.5,
        }
        return weights.get(link_type, 0.3)

    def _louvain_clustering(self, G: nx.Graph) -> list[set]:
        """Run Louvain community detection."""
        try:
            from networkx.algorithms.community import louvain_communities

            resolution = self._settings.cluster_detection.resolution
            return louvain_communities(G, weight="weight", resolution=resolution)
        except ImportError:
            # Fallback to connected components
            return [set(c) for c in nx.connected_components(G)]

    def _label_propagation(self, G: nx.Graph) -> list[set]:
        """Run label propagation clustering."""
        from networkx.algorithms.community import label_propagation_communities

        return list(label_propagation_communities(G))

    def _analyze_cluster(
        self,
        G: nx.Graph,
        members: list[str],
        cluster_id: str,
    ) -> SyntheticCluster:
        """Analyze a detected cluster."""
        # Find shared elements
        shared_elements = {"ssn": 0, "address": 0, "phone": 0, "device": 0}
        for i, m1 in enumerate(members):
            for m2 in members[i + 1 :]:
                if G.has_edge(m1, m2):
                    for link_type in G[m1][m2]["shared_types"]:
                        shared_elements[link_type] = (
                            shared_elements.get(link_type, 0) + 1
                        )

        # Find center (most connected)
        subgraph = G.subgraph(members)
        center = max(members, key=lambda x: subgraph.degree(x))

        # Calculate cluster score
        cluster_score = self._calculate_cluster_score(
            len(members), shared_elements, subgraph
        )

        # Determine risk level
        if cluster_score >= 0.8:
            risk_level = "critical"
        elif cluster_score >= 0.6:
            risk_level = "high"
        elif cluster_score >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        return SyntheticCluster(
            cluster_id=cluster_id,
            member_count=len(members),
            member_identities=members,
            shared_elements=shared_elements,
            cluster_score=cluster_score,
            center_identity=center,
            risk_level=risk_level,
        )

    def _calculate_cluster_score(
        self,
        member_count: int,
        shared_elements: dict,
        subgraph: nx.Graph,
    ) -> float:
        """Calculate synthetic probability for a cluster."""
        score = 0.0

        # SSN sharing is extremely suspicious
        if shared_elements.get("ssn", 0) > 0:
            score += 0.5

        # Many members sharing phones
        if shared_elements.get("phone", 0) > member_count:
            score += 0.2

        # Device sharing
        if shared_elements.get("device", 0) > 0:
            score += 0.15

        # Cluster density (how interconnected)
        density = nx.density(subgraph)
        score += density * 0.15

        # Size factor (larger clusters more suspicious)
        if member_count >= 10:
            score += 0.1
        elif member_count >= 5:
            score += 0.05

        return min(1.0, score)

    def get_cluster_members(self, cluster_id: str) -> list[str]:
        """Get member identities for a cluster."""
        if not self._driver:
            return []

        with self._driver.session() as session:
            query = """
            MATCH (i:Identity {cluster_id: $cluster_id})
            RETURN i.identity_id as identity_id
            """
            result = session.run(query, cluster_id=cluster_id)
            return [record["identity_id"] for record in result]
