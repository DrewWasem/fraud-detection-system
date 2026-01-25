#!/usr/bin/env python3
"""Train the bust-out prediction model."""

import argparse
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data(data_path: str, lookback_months: int = 12) -> pd.DataFrame:
    """Load credit sequence data."""
    logger.info(f"Loading data from {data_path}")
    df = pd.read_parquet(data_path)
    logger.info(f"Lookback period: {lookback_months} months")
    return df


def extract_sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract features from credit sequences."""
    features = []

    for _, row in df.iterrows():
        balances = np.array(row.get("monthly_balances", []))
        payments = np.array(row.get("monthly_payments", []))
        utilization = np.array(row.get("utilization_rates", []))
        cash_advances = np.array(row.get("cash_advance_amounts", []))

        feat = {
            "account_id": row["account_id"],
            "is_bust_out": row.get("is_bust_out", 0),
        }

        # Balance features
        if len(balances) >= 3:
            feat["balance_trend"] = np.polyfit(range(len(balances)), balances, 1)[0]
            feat["balance_volatility"] = np.std(balances)
            feat["max_balance"] = np.max(balances)

        # Payment features
        if len(payments) >= 3:
            feat["avg_payment"] = np.mean(payments)
            feat["payment_trend"] = np.polyfit(range(len(payments)), payments, 1)[0]
            feat["declining_payments"] = int(
                np.mean(payments[-3:]) < np.mean(payments[:-3]) * 0.8
                if len(payments) >= 6 else False
            )

        # Utilization features
        if len(utilization) >= 3:
            feat["avg_utilization"] = np.mean(utilization)
            feat["max_utilization"] = np.max(utilization)
            feat["utilization_trend"] = np.polyfit(range(len(utilization)), utilization, 1)[0]

        # Cash advance features
        if len(cash_advances) > 0:
            feat["total_cash_advances"] = np.sum(cash_advances)
            feat["cash_advance_frequency"] = np.sum(cash_advances > 0)

        feat["months_on_books"] = row.get("months_on_books", 0)
        features.append(feat)

    return pd.DataFrame(features)


def main():
    parser = argparse.ArgumentParser(description="Train bust-out model")
    parser.add_argument("--data", required=True, help="Training data path")
    parser.add_argument("--lookback-months", type=int, default=12)
    parser.add_argument("--output", required=True, help="Output model path")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    # Load data
    df = load_data(args.data, args.lookback_months)
    logger.info(f"Loaded {len(df)} accounts")

    # Extract features
    features_df = extract_sequence_features(df)
    logger.info(f"Extracted features for {len(features_df)} accounts")

    # Prepare for training
    feature_cols = [c for c in features_df.columns if c not in ["account_id", "is_bust_out"]]
    X = features_df[feature_cols].fillna(0)
    y = features_df["is_bust_out"].astype(int)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )

    # Train
    logger.info("Training model...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    logger.info(f"ROC AUC: {roc_auc_score(y_test, y_proba):.4f}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    logger.info(f"Model saved to {output_path}")


if __name__ == "__main__":
    main()
