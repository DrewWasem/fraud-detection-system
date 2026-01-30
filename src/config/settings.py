"""Application configuration settings."""

import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringSettings(BaseSettings):
    """Scoring model configuration."""

    ssn_signals_weight: float = 0.25
    graph_features_weight: float = 0.30
    velocity_signals_weight: float = 0.20
    credit_behavior_weight: float = 0.15
    device_binding_weight: float = 0.10

    high_risk_threshold: float = 0.80
    medium_risk_threshold: float = 0.50
    review_threshold: float = 0.30


class BustOutSettings(BaseSettings):
    """Bust-out prediction configuration."""

    lookback_months: int = 12
    prediction_window_days: int = 90
    threshold: float = 0.75


class Neo4jSettings(BaseSettings):
    """Neo4j connection configuration."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    uri: str = Field(default="bolt://localhost:7687")
    user: str = Field(default="neo4j")
    password: str = Field(default="")


class EntityResolutionSettings(BaseSettings):
    """Entity resolution configuration."""

    ssn_weight: float = 1.0
    name_weight: float = 0.3
    address_weight: float = 0.4
    phone_weight: float = 0.3
    email_weight: float = 0.2
    similarity_threshold: float = 0.85


class ClusterDetectionSettings(BaseSettings):
    """Cluster detection configuration."""

    algorithm: str = "louvain"
    min_cluster_size: int = 3
    resolution: float = 1.0


class VelocitySettings(BaseSettings):
    """PII velocity thresholds."""

    address_max_identities_6mo: int = 5
    phone_max_identities_6mo: int = 3
    email_max_identities_6mo: int = 2


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""

    # Velocity key prefixes
    address_prefix: str = "velocity:address"
    phone_prefix: str = "velocity:phone"
    email_prefix: str = "velocity:email"
    device_prefix: str = "velocity:device"

    # TTL for velocity data (in seconds)
    velocity_ttl: int = 180 * 24 * 60 * 60  # 180 days


class KafkaSettings(BaseSettings):
    """Kafka configuration."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    applications_topic: str = "credit-applications"
    scores_topic: str = "synthetic-scores"
    alerts_topic: str = "bust-out-alerts"


class Settings(BaseSettings):
    """Main application settings."""

    app_name: str = "Synthetic Identity Fraud Detection"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Sub-configurations
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    bust_out: BustOutSettings = Field(default_factory=BustOutSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    entity_resolution: EntityResolutionSettings = Field(
        default_factory=EntityResolutionSettings
    )
    cluster_detection: ClusterDetectionSettings = Field(
        default_factory=ClusterDetectionSettings
    )
    velocity: VelocitySettings = Field(default_factory=VelocitySettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    models_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "models")
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
