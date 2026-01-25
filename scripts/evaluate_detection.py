#!/usr/bin/env python3
"""Evaluate detection model performance."""

import argparse
import logging

import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_curve,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_synthetic_detection(predictions_path: str, labels_path: str):
    """Evaluate synthetic identity detection."""
    logger.info("Evaluating synthetic detection...")

    predictions = pd.read_parquet(predictions_path)
    labels = pd.read_parquet(labels_path)

    merged = predictions.merge(labels, on="identity_id")

    y_true = merged["is_synthetic"]
    y_score = merged["synthetic_score"]
    y_pred = (y_score >= 0.5).astype(int)

    # Classification report
    logger.info("\nClassification Report:")
    print(classification_report(y_true, y_pred))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    logger.info(f"\nConfusion Matrix:\n{cm}")

    # ROC AUC
    auc = roc_auc_score(y_true, y_score)
    logger.info(f"\nROC AUC: {auc:.4f}")

    # Detection rate at different thresholds
    for threshold in [0.3, 0.5, 0.7, 0.8, 0.9]:
        y_pred_t = (y_score >= threshold).astype(int)
        tp = ((y_pred_t == 1) & (y_true == 1)).sum()
        fn = ((y_pred_t == 0) & (y_true == 1)).sum()
        fp = ((y_pred_t == 1) & (y_true == 0)).sum()

        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0

        logger.info(f"Threshold {threshold}: Recall={recall:.2%}, Precision={precision:.2%}")


def evaluate_bust_out_prediction(predictions_path: str, outcomes_path: str):
    """Evaluate bust-out prediction."""
    logger.info("Evaluating bust-out prediction...")

    predictions = pd.read_parquet(predictions_path)
    outcomes = pd.read_parquet(outcomes_path)

    merged = predictions.merge(outcomes, on="account_id")

    y_true = merged["is_bust_out"]
    y_score = merged["bust_out_probability"]

    auc = roc_auc_score(y_true, y_score)
    logger.info(f"ROC AUC: {auc:.4f}")

    # Lead time analysis for true positives
    predicted_correct = merged[(y_score >= 0.5) & (y_true == 1)]
    if len(predicted_correct) > 0 and "prediction_date" in merged.columns:
        lead_times = (
            pd.to_datetime(predicted_correct["bust_out_date"]) -
            pd.to_datetime(predicted_correct["prediction_date"])
        ).dt.days

        logger.info(f"\nLead Time Analysis (True Positives):")
        logger.info(f"  Mean: {lead_times.mean():.1f} days")
        logger.info(f"  Median: {lead_times.median():.1f} days")
        logger.info(f"  >30 days: {(lead_times > 30).mean():.1%}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection models")
    parser.add_argument("--type", choices=["synthetic", "bust-out"], required=True)
    parser.add_argument("--predictions", required=True, help="Predictions file")
    parser.add_argument("--labels", required=True, help="Ground truth labels")
    args = parser.parse_args()

    if args.type == "synthetic":
        evaluate_synthetic_detection(args.predictions, args.labels)
    else:
        evaluate_bust_out_prediction(args.predictions, args.labels)


if __name__ == "__main__":
    main()
