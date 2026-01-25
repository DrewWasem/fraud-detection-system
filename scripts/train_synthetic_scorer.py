#!/usr/bin/env python3
"""Train the synthetic identity scorer model."""

import argparse
import logging
from pathlib import Path

import pandas as pd
import joblib
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data(data_path: str, graph_features_path: str = None) -> pd.DataFrame:
    """Load training data."""
    logger.info(f"Loading data from {data_path}")
    df = pd.read_parquet(data_path)

    if graph_features_path:
        logger.info(f"Loading graph features from {graph_features_path}")
        graph_df = pd.read_parquet(graph_features_path)
        df = df.merge(graph_df, on="identity_id", how="left")

    return df


def prepare_features(df: pd.DataFrame) -> tuple:
    """Prepare features and labels."""
    feature_columns = [
        "ssn_score", "graph_score", "velocity_score",
        "credit_behavior_score", "device_score",
        "shared_ssn_count", "shared_address_count",
        "shared_phone_count", "cluster_size",
        "au_ratio", "file_age_months",
    ]

    # Filter to available columns
    available_features = [c for c in feature_columns if c in df.columns]
    logger.info(f"Using features: {available_features}")

    X = df[available_features].fillna(0)
    y = df["is_synthetic"].astype(int)

    return X, y


def train_model(X_train, y_train):
    """Train the model."""
    logger.info("Training model...")
    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    """Evaluate model performance."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    auc = roc_auc_score(y_test, y_proba)
    logger.info(f"ROC AUC: {auc:.4f}")

    return {"auc": auc}


def main():
    parser = argparse.ArgumentParser(description="Train synthetic scorer")
    parser.add_argument("--data", required=True, help="Training data path")
    parser.add_argument("--graph-features", help="Graph features path")
    parser.add_argument("--output", required=True, help="Output model path")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    # Load data
    df = load_data(args.data, args.graph_features)
    logger.info(f"Loaded {len(df)} samples")

    # Prepare features
    X, y = prepare_features(df)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Train model
    model = train_model(X_train, y_train)

    # Evaluate
    metrics = evaluate_model(model, X_test, y_test)

    # Save model
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    logger.info(f"Model saved to {output_path}")


if __name__ == "__main__":
    main()
