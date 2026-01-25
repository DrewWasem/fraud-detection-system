"""Neo4j identity graph management."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from neo4j import GraphDatabase

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class IdentityNode:
    """Identity node in the graph."""

    identity_id: str
    ssn_hash: str
    name_hash: str
    dob: datetime
    first_seen: datetime
    last_seen: datetime
    synthetic_score: Optional[float] = None
    cluster_id: Optional[str] = None


@dataclass
class RelationshipEdge:
    """Edge between identity elements."""

    source_id: str
    target_id: str
    relationship_type: str
    weight: float
    first_seen: datetime
    properties: dict


class IdentityGraph:
    """Manages the Neo4j identity graph."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        settings = get_settings()
        self.uri = uri or settings.neo4j.uri
        self.user = user or settings.neo4j.user
        self.password = password or settings.neo4j.password
        self._driver = None

    def connect(self) -> None:
        """Connect to Neo4j database."""
        self._driver = GraphDatabase.driver(
            self.uri, auth=(self.user, self.password)
        )
        logger.info(f"Connected to Neo4j at {self.uri}")

    def close(self) -> None:
        """Close the database connection."""
        if self._driver:
            self._driver.close()
            logger.info("Neo4j connection closed")

    def create_schema(self) -> None:
        """Create graph schema and indexes."""
        with self._driver.session() as session:
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT identity_id IF NOT EXISTS FOR (i:Identity) REQUIRE i.identity_id IS UNIQUE",
                "CREATE CONSTRAINT ssn_hash IF NOT EXISTS FOR (s:SSN) REQUIRE s.hash IS UNIQUE",
                "CREATE CONSTRAINT address_hash IF NOT EXISTS FOR (a:Address) REQUIRE a.hash IS UNIQUE",
                "CREATE CONSTRAINT phone_hash IF NOT EXISTS FOR (p:Phone) REQUIRE p.hash IS UNIQUE",
                "CREATE CONSTRAINT email_hash IF NOT EXISTS FOR (e:Email) REQUIRE e.hash IS UNIQUE",
                "CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE",
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint creation failed: {e}")

            # Create indexes
            indexes = [
                "CREATE INDEX identity_cluster IF NOT EXISTS FOR (i:Identity) ON (i.cluster_id)",
                "CREATE INDEX identity_synthetic IF NOT EXISTS FOR (i:Identity) ON (i.synthetic_score)",
            ]

            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    logger.warning(f"Index creation failed: {e}")

        logger.info("Graph schema created")

    def add_identity(
        self,
        identity_id: str,
        ssn_hash: str,
        name_hash: str,
        dob: datetime,
        address_hash: str,
        phone_hash: str,
        email_hash: str,
        device_fingerprint: Optional[str] = None,
    ) -> None:
        """
        Add an identity and its elements to the graph.

        Creates nodes for the identity and all PII elements,
        and links them with relationships.
        """
        with self._driver.session() as session:
            query = """
            MERGE (i:Identity {identity_id: $identity_id})
            SET i.name_hash = $name_hash,
                i.dob = $dob,
                i.first_seen = coalesce(i.first_seen, $now),
                i.last_seen = $now

            MERGE (s:SSN {hash: $ssn_hash})
            MERGE (a:Address {hash: $address_hash})
            MERGE (p:Phone {hash: $phone_hash})
            MERGE (e:Email {hash: $email_hash})

            MERGE (i)-[r1:HAS_SSN]->(s)
            SET r1.first_seen = coalesce(r1.first_seen, $now)

            MERGE (i)-[r2:HAS_ADDRESS]->(a)
            SET r2.first_seen = coalesce(r2.first_seen, $now),
                r2.last_seen = $now

            MERGE (i)-[r3:HAS_PHONE]->(p)
            SET r3.first_seen = coalesce(r3.first_seen, $now),
                r3.last_seen = $now

            MERGE (i)-[r4:HAS_EMAIL]->(e)
            SET r4.first_seen = coalesce(r4.first_seen, $now),
                r4.last_seen = $now

            RETURN i.identity_id
            """

            now = datetime.now()
            session.run(
                query,
                identity_id=identity_id,
                ssn_hash=ssn_hash,
                name_hash=name_hash,
                dob=dob.isoformat(),
                address_hash=address_hash,
                phone_hash=phone_hash,
                email_hash=email_hash,
                now=now.isoformat(),
            )

            # Add device if provided
            if device_fingerprint:
                device_query = """
                MATCH (i:Identity {identity_id: $identity_id})
                MERGE (d:Device {fingerprint: $device_fp})
                MERGE (i)-[r:USES_DEVICE]->(d)
                SET r.first_seen = coalesce(r.first_seen, $now),
                    r.last_seen = $now
                """
                session.run(
                    device_query,
                    identity_id=identity_id,
                    device_fp=device_fingerprint,
                    now=now.isoformat(),
                )

        logger.debug(f"Added identity {identity_id[:8]} to graph")

    def get_identity_graph(
        self, identity_id: str, depth: int = 2
    ) -> dict:
        """
        Get the subgraph around an identity.

        Args:
            identity_id: Identity to center on
            depth: How many hops to traverse

        Returns:
            dict with nodes and edges
        """
        with self._driver.session() as session:
            query = """
            MATCH path = (i:Identity {identity_id: $identity_id})-[*1..$depth]-(connected)
            WITH nodes(path) as nodes, relationships(path) as rels
            UNWIND nodes as n
            WITH COLLECT(DISTINCT n) as allNodes, rels
            UNWIND rels as r
            WITH allNodes, COLLECT(DISTINCT r) as allRels
            RETURN allNodes, allRels
            """

            result = session.run(query, identity_id=identity_id, depth=depth)
            record = result.single()

            if not record:
                return {"nodes": [], "edges": []}

            nodes = []
            for node in record["allNodes"]:
                nodes.append({
                    "id": node.element_id,
                    "labels": list(node.labels),
                    "properties": dict(node),
                })

            edges = []
            for rel in record["allRels"]:
                edges.append({
                    "source": rel.start_node.element_id,
                    "target": rel.end_node.element_id,
                    "type": rel.type,
                    "properties": dict(rel),
                })

            return {"nodes": nodes, "edges": edges}

    def find_shared_elements(
        self, identity_id: str
    ) -> dict:
        """
        Find identities sharing PII elements with the given identity.

        Returns:
            dict with shared SSNs, addresses, phones, emails
        """
        with self._driver.session() as session:
            query = """
            MATCH (i:Identity {identity_id: $identity_id})

            OPTIONAL MATCH (i)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(other1:Identity)
            WHERE other1 <> i
            WITH i, COLLECT(DISTINCT other1.identity_id) as shared_ssn

            OPTIONAL MATCH (i)-[:HAS_ADDRESS]->(a:Address)<-[:HAS_ADDRESS]-(other2:Identity)
            WHERE other2 <> i
            WITH i, shared_ssn, COLLECT(DISTINCT other2.identity_id) as shared_address

            OPTIONAL MATCH (i)-[:HAS_PHONE]->(p:Phone)<-[:HAS_PHONE]-(other3:Identity)
            WHERE other3 <> i
            WITH i, shared_ssn, shared_address, COLLECT(DISTINCT other3.identity_id) as shared_phone

            OPTIONAL MATCH (i)-[:HAS_EMAIL]->(e:Email)<-[:HAS_EMAIL]-(other4:Identity)
            WHERE other4 <> i

            RETURN shared_ssn, shared_address, shared_phone,
                   COLLECT(DISTINCT other4.identity_id) as shared_email
            """

            result = session.run(query, identity_id=identity_id)
            record = result.single()

            if not record:
                return {
                    "shared_ssn": [],
                    "shared_address": [],
                    "shared_phone": [],
                    "shared_email": [],
                }

            return {
                "shared_ssn": record["shared_ssn"] or [],
                "shared_address": record["shared_address"] or [],
                "shared_phone": record["shared_phone"] or [],
                "shared_email": record["shared_email"] or [],
            }

    def update_synthetic_score(
        self, identity_id: str, score: float
    ) -> None:
        """Update the synthetic score for an identity."""
        with self._driver.session() as session:
            query = """
            MATCH (i:Identity {identity_id: $identity_id})
            SET i.synthetic_score = $score,
                i.score_updated = $now
            """
            session.run(
                query,
                identity_id=identity_id,
                score=score,
                now=datetime.now().isoformat(),
            )

    def assign_cluster(
        self, identity_id: str, cluster_id: str
    ) -> None:
        """Assign an identity to a cluster."""
        with self._driver.session() as session:
            query = """
            MATCH (i:Identity {identity_id: $identity_id})
            SET i.cluster_id = $cluster_id
            """
            session.run(query, identity_id=identity_id, cluster_id=cluster_id)
