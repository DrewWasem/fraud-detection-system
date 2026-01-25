"""Graph Neural Network for synthetic identity detection."""

import logging
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class GNNLayer(nn.Module):
    """Graph Neural Network layer."""

    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)
        self.attention = nn.Linear(2 * out_features, 1)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node features [num_nodes, in_features]
            edge_index: Edge indices [2, num_edges]
            edge_weight: Optional edge weights [num_edges]

        Returns:
            Updated node features [num_nodes, out_features]
        """
        # Transform features
        h = self.linear(x)

        # Message passing with attention
        row, col = edge_index
        h_i = h[row]
        h_j = h[col]

        # Compute attention scores
        attention_input = torch.cat([h_i, h_j], dim=-1)
        attention_scores = F.leaky_relu(self.attention(attention_input))
        attention_scores = F.softmax(attention_scores, dim=0)

        if edge_weight is not None:
            attention_scores = attention_scores * edge_weight.unsqueeze(-1)

        # Aggregate messages
        messages = attention_scores * h_j
        aggregated = torch.zeros_like(h)
        aggregated.index_add_(0, row, messages)

        # Combine with self-loop
        output = F.relu(h + aggregated)
        return output


class IdentityGNN(nn.Module):
    """Graph Neural Network for synthetic identity scoring."""

    def __init__(
        self,
        input_dim: int = 12,
        hidden_dim: int = 64,
        output_dim: int = 1,
        num_layers: int = 3,
        dropout: float = 0.2,
    ):
        """
        Initialize GNN model.

        Args:
            input_dim: Input feature dimension
            hidden_dim: Hidden layer dimension
            output_dim: Output dimension (1 for binary classification)
            num_layers: Number of GNN layers
            dropout: Dropout rate
        """
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout

        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)

        # GNN layers
        self.gnn_layers = nn.ModuleList(
            [GNNLayer(hidden_dim, hidden_dim) for _ in range(num_layers)]
        )

        # Layer normalization
        self.layer_norms = nn.ModuleList(
            [nn.LayerNorm(hidden_dim) for _ in range(num_layers)]
        )

        # Output layers
        self.output_layers = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.Sigmoid(),
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node features [num_nodes, input_dim]
            edge_index: Edge indices [2, num_edges]
            edge_weight: Optional edge weights

        Returns:
            Synthetic scores [num_nodes, 1]
        """
        # Input projection
        h = self.input_proj(x)

        # GNN layers with residual connections
        for i, (gnn, norm) in enumerate(zip(self.gnn_layers, self.layer_norms)):
            h_new = gnn(h, edge_index, edge_weight)
            h_new = norm(h_new)
            h_new = F.dropout(h_new, p=self.dropout, training=self.training)
            h = h + h_new  # Residual connection

        # Output
        return self.output_layers(h)

    def get_embeddings(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Get node embeddings before final classification.

        Args:
            x: Node features
            edge_index: Edge indices
            edge_weight: Optional edge weights

        Returns:
            Node embeddings [num_nodes, hidden_dim]
        """
        h = self.input_proj(x)

        for gnn, norm in zip(self.gnn_layers, self.layer_norms):
            h_new = gnn(h, edge_index, edge_weight)
            h_new = norm(h_new)
            h = h + h_new

        return h


class GNNTrainer:
    """Trainer for the Identity GNN model."""

    def __init__(
        self,
        model: IdentityGNN,
        learning_rate: float = 0.001,
        weight_decay: float = 1e-5,
    ):
        self.model = model
        self.optimizer = torch.optim.Adam(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        self.criterion = nn.BCELoss()

    def train_epoch(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        labels: torch.Tensor,
        train_mask: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> float:
        """Train for one epoch."""
        self.model.train()
        self.optimizer.zero_grad()

        out = self.model(x, edge_index, edge_weight)
        loss = self.criterion(out[train_mask], labels[train_mask])

        loss.backward()
        self.optimizer.step()

        return loss.item()

    def evaluate(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        labels: torch.Tensor,
        mask: torch.Tensor,
        edge_weight: Optional[torch.Tensor] = None,
    ) -> dict:
        """Evaluate model."""
        self.model.eval()

        with torch.no_grad():
            out = self.model(x, edge_index, edge_weight)
            predictions = (out[mask] > 0.5).float()
            labels_masked = labels[mask]

            accuracy = (predictions == labels_masked).float().mean().item()
            loss = self.criterion(out[mask], labels_masked).item()

            # Calculate precision/recall
            tp = ((predictions == 1) & (labels_masked == 1)).sum().item()
            fp = ((predictions == 1) & (labels_masked == 0)).sum().item()
            fn = ((predictions == 0) & (labels_masked == 1)).sum().item()

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

        return {
            "loss": loss,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    def save(self, path: str) -> None:
        """Save model checkpoint."""
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
            },
            path,
        )

    def load(self, path: str) -> None:
        """Load model checkpoint."""
        checkpoint = torch.load(path)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
