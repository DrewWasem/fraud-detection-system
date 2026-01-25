"""Identity graph visualization."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GraphVisualization:
    """Graph visualization data."""
    nodes: list[dict]
    edges: list[dict]
    layout: str
    metadata: dict


class GraphVisualizer:
    """Generates identity graph visualizations."""

    def __init__(self, graph_client=None):
        self._graph = graph_client

    def visualize_identity(
        self,
        identity_id: str,
        depth: int = 2,
        layout: str = "force",
    ) -> GraphVisualization:
        """Generate visualization for identity subgraph."""
        # Get graph data
        graph_data = self._get_subgraph(identity_id, depth)

        # Format nodes
        nodes = self._format_nodes(graph_data.get("nodes", []))

        # Format edges
        edges = self._format_edges(graph_data.get("edges", []))

        return GraphVisualization(
            nodes=nodes,
            edges=edges,
            layout=layout,
            metadata={
                "center_identity": identity_id,
                "depth": depth,
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        )

    def visualize_cluster(
        self,
        cluster_id: str,
        layout: str = "force",
    ) -> GraphVisualization:
        """Generate visualization for a cluster."""
        # Get cluster members
        members = self._get_cluster_members(cluster_id)

        # Build visualization for cluster
        nodes = []
        edges = []

        for member in members:
            subgraph = self._get_subgraph(member, depth=1)
            nodes.extend(self._format_nodes(subgraph.get("nodes", [])))
            edges.extend(self._format_edges(subgraph.get("edges", [])))

        # Deduplicate
        seen_nodes = set()
        unique_nodes = []
        for node in nodes:
            if node["id"] not in seen_nodes:
                unique_nodes.append(node)
                seen_nodes.add(node["id"])

        return GraphVisualization(
            nodes=unique_nodes,
            edges=edges,
            layout=layout,
            metadata={
                "cluster_id": cluster_id,
                "member_count": len(members),
            },
        )

    def _get_subgraph(self, identity_id: str, depth: int) -> dict:
        """Get subgraph from Neo4j."""
        if self._graph:
            return self._graph.get_identity_graph(identity_id, depth)
        return {"nodes": [], "edges": []}

    def _get_cluster_members(self, cluster_id: str) -> list[str]:
        """Get cluster member IDs."""
        return []

    def _format_nodes(self, nodes: list[dict]) -> list[dict]:
        """Format nodes for visualization."""
        formatted = []
        for node in nodes:
            labels = node.get("labels", [])
            node_type = labels[0] if labels else "unknown"

            formatted.append({
                "id": node.get("id"),
                "type": node_type,
                "label": self._get_node_label(node),
                "properties": node.get("properties", {}),
                "color": self._get_node_color(node_type),
                "size": self._get_node_size(node_type),
            })
        return formatted

    def _format_edges(self, edges: list[dict]) -> list[dict]:
        """Format edges for visualization."""
        return [
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "type": edge.get("type"),
                "properties": edge.get("properties", {}),
            }
            for edge in edges
        ]

    def _get_node_label(self, node: dict) -> str:
        """Get display label for node."""
        props = node.get("properties", {})
        labels = node.get("labels", [])

        if "Identity" in labels:
            return f"ID: {props.get('identity_id', 'unknown')[:8]}"
        elif "SSN" in labels:
            return "SSN"
        elif "Address" in labels:
            return "Address"
        elif "Phone" in labels:
            return "Phone"
        elif "Email" in labels:
            return "Email"
        elif "Device" in labels:
            return "Device"
        return "Unknown"

    def _get_node_color(self, node_type: str) -> str:
        """Get color for node type."""
        colors = {
            "Identity": "#ff6b6b",
            "SSN": "#4ecdc4",
            "Address": "#45b7d1",
            "Phone": "#96ceb4",
            "Email": "#ffeaa7",
            "Device": "#dfe6e9",
        }
        return colors.get(node_type, "#95a5a6")

    def _get_node_size(self, node_type: str) -> int:
        """Get size for node type."""
        sizes = {
            "Identity": 30,
            "SSN": 20,
            "Address": 20,
            "Phone": 20,
            "Email": 20,
            "Device": 20,
        }
        return sizes.get(node_type, 15)
