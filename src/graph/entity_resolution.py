"""Fuzzy identity matching and entity resolution."""

import logging
from dataclasses import dataclass
from typing import Optional

import jellyfish

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """Potential identity match."""

    identity_id_1: str
    identity_id_2: str
    similarity_score: float
    match_components: dict
    is_match: bool


@dataclass
class ResolvedEntity:
    """Resolved entity linking multiple identity records."""

    entity_id: str
    identity_ids: list[str]
    primary_identity: str
    confidence: float


class EntityResolver:
    """Resolves and links identity records."""

    def __init__(self):
        self._settings = get_settings()

    def calculate_similarity(
        self,
        identity_1: dict,
        identity_2: dict,
    ) -> MatchCandidate:
        """
        Calculate similarity between two identity records.

        Args:
            identity_1: First identity record
            identity_2: Second identity record

        Returns:
            MatchCandidate with similarity analysis
        """
        weights = self._settings.entity_resolution
        match_components = {}
        total_weight = 0.0
        weighted_score = 0.0

        # SSN comparison (exact match only)
        if identity_1.get("ssn_hash") and identity_2.get("ssn_hash"):
            ssn_match = identity_1["ssn_hash"] == identity_2["ssn_hash"]
            match_components["ssn"] = 1.0 if ssn_match else 0.0
            weighted_score += match_components["ssn"] * weights.ssn_weight
            total_weight += weights.ssn_weight

        # Name comparison (fuzzy)
        name_sim = self._compare_names(
            identity_1.get("first_name", ""),
            identity_1.get("last_name", ""),
            identity_2.get("first_name", ""),
            identity_2.get("last_name", ""),
        )
        match_components["name"] = name_sim
        weighted_score += name_sim * weights.name_weight
        total_weight += weights.name_weight

        # Address comparison (fuzzy)
        addr_sim = self._compare_addresses(
            identity_1.get("address", {}),
            identity_2.get("address", {}),
        )
        match_components["address"] = addr_sim
        weighted_score += addr_sim * weights.address_weight
        total_weight += weights.address_weight

        # Phone comparison
        phone_sim = self._compare_phones(
            identity_1.get("phone", ""),
            identity_2.get("phone", ""),
        )
        match_components["phone"] = phone_sim
        weighted_score += phone_sim * weights.phone_weight
        total_weight += weights.phone_weight

        # Email comparison
        email_sim = self._compare_emails(
            identity_1.get("email", ""),
            identity_2.get("email", ""),
        )
        match_components["email"] = email_sim
        weighted_score += email_sim * weights.email_weight
        total_weight += weights.email_weight

        # Calculate overall similarity
        overall_similarity = weighted_score / total_weight if total_weight > 0 else 0.0

        # Determine if match
        is_match = overall_similarity >= weights.similarity_threshold

        return MatchCandidate(
            identity_id_1=identity_1.get("identity_id", ""),
            identity_id_2=identity_2.get("identity_id", ""),
            similarity_score=overall_similarity,
            match_components=match_components,
            is_match=is_match,
        )

    def _compare_names(
        self,
        first1: str,
        last1: str,
        first2: str,
        last2: str,
    ) -> float:
        """Compare names using fuzzy matching."""
        if not (first1 and first2 and last1 and last2):
            return 0.0

        # Jaro-Winkler similarity
        first_sim = jellyfish.jaro_winkler_similarity(
            first1.lower(), first2.lower()
        )
        last_sim = jellyfish.jaro_winkler_similarity(
            last1.lower(), last2.lower()
        )

        # Also check for name transposition
        transposed_sim = max(
            jellyfish.jaro_winkler_similarity(first1.lower(), last2.lower()),
            jellyfish.jaro_winkler_similarity(last1.lower(), first2.lower()),
        )

        # Take the best match
        return max((first_sim + last_sim) / 2, transposed_sim * 0.8)

    def _compare_addresses(
        self,
        addr1: dict,
        addr2: dict,
    ) -> float:
        """Compare addresses with fuzzy matching."""
        if not addr1 or not addr2:
            return 0.0

        scores = []

        # Compare ZIP (exact or prefix)
        zip1 = str(addr1.get("zip", ""))[:5]
        zip2 = str(addr2.get("zip", ""))[:5]
        if zip1 and zip2:
            scores.append(1.0 if zip1 == zip2 else 0.0)

        # Compare city
        city1 = addr1.get("city", "").lower()
        city2 = addr2.get("city", "").lower()
        if city1 and city2:
            scores.append(jellyfish.jaro_winkler_similarity(city1, city2))

        # Compare street
        street1 = addr1.get("street", "").lower()
        street2 = addr2.get("street", "").lower()
        if street1 and street2:
            scores.append(jellyfish.jaro_winkler_similarity(street1, street2))

        return sum(scores) / len(scores) if scores else 0.0

    def _compare_phones(self, phone1: str, phone2: str) -> float:
        """Compare phone numbers."""
        if not phone1 or not phone2:
            return 0.0

        # Normalize to digits only
        import re

        digits1 = re.sub(r"\D", "", phone1)
        digits2 = re.sub(r"\D", "", phone2)

        # Remove country code if present
        if len(digits1) == 11 and digits1.startswith("1"):
            digits1 = digits1[1:]
        if len(digits2) == 11 and digits2.startswith("1"):
            digits2 = digits2[1:]

        return 1.0 if digits1 == digits2 else 0.0

    def _compare_emails(self, email1: str, email2: str) -> float:
        """Compare email addresses."""
        if not email1 or not email2:
            return 0.0

        email1_lower = email1.lower()
        email2_lower = email2.lower()

        if email1_lower == email2_lower:
            return 1.0

        # Check local part similarity (before @)
        local1 = email1_lower.split("@")[0]
        local2 = email2_lower.split("@")[0]

        return jellyfish.jaro_winkler_similarity(local1, local2) * 0.7

    def find_matches(
        self,
        identity: dict,
        candidates: list[dict],
        threshold: Optional[float] = None,
    ) -> list[MatchCandidate]:
        """
        Find matching identities from a list of candidates.

        Args:
            identity: Identity to match
            candidates: List of candidate identities
            threshold: Optional custom threshold

        Returns:
            List of matches above threshold
        """
        if threshold is None:
            threshold = self._settings.entity_resolution.similarity_threshold

        matches = []
        for candidate in candidates:
            if candidate.get("identity_id") == identity.get("identity_id"):
                continue

            match = self.calculate_similarity(identity, candidate)
            if match.similarity_score >= threshold:
                matches.append(match)

        # Sort by similarity descending
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches

    def resolve_entities(
        self,
        identities: list[dict],
    ) -> list[ResolvedEntity]:
        """
        Resolve a list of identities into distinct entities.

        Uses transitive closure to group matching identities.

        Args:
            identities: List of identity records

        Returns:
            List of resolved entities
        """
        # Build match graph
        import networkx as nx

        G = nx.Graph()

        for i, id1 in enumerate(identities):
            G.add_node(id1.get("identity_id"))
            for id2 in identities[i + 1 :]:
                match = self.calculate_similarity(id1, id2)
                if match.is_match:
                    G.add_edge(
                        id1.get("identity_id"),
                        id2.get("identity_id"),
                        weight=match.similarity_score,
                    )

        # Find connected components (entity clusters)
        resolved = []
        for component in nx.connected_components(G):
            identity_ids = list(component)
            # Primary is the one with most connections
            primary = max(
                identity_ids,
                key=lambda x: G.degree(x),
            )

            # Average edge weight as confidence
            edges = G.edges(identity_ids, data=True)
            if edges:
                confidence = sum(e[2]["weight"] for e in edges) / len(list(edges))
            else:
                confidence = 1.0

            resolved.append(
                ResolvedEntity(
                    entity_id=f"entity_{primary[:8]}",
                    identity_ids=identity_ids,
                    primary_identity=primary,
                    confidence=confidence,
                )
            )

        return resolved
