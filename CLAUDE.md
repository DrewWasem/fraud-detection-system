# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Synthetic Identity Fraud Detection** is a specialized fraud detection platform focused on detecting synthetic identities—fabricated personas combining real and fake PII elements. Unlike traditional transaction fraud, synthetic identity fraud involves creating entirely new "people" who build credit over months/years before "busting out."

**Key Differentiators:**
- Graph-based identity resolution linking SSN, address, phone, email clusters
- PII velocity analysis (how fast identity elements spread across applications)
- Synthetic identity scoring using cross-institution data patterns
- Bust-out prediction before it happens
- Dark web credential monitoring integration
- Identity element age analysis (SSN issuance year vs. claimed age)
- Device-identity binding strength scoring

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 IDENTITY ELEMENT INGESTION                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   SSN    │  │ Address  │  │  Phone   │  │  Email   │       │
│  │ Analysis │  │ Analysis │  │ Analysis │  │ Analysis │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼───────────────┘
        └─────────────┴──────┬──────┴─────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   IDENTITY GRAPH ENGINE                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  Neo4j Identity Graph                      │ │
│  │                                                            │ │
│  │    [SSN-1234] ←─shares_address─→ [SSN-5678]              │ │
│  │        │                              │                    │ │
│  │    uses_phone                    uses_phone               │ │
│  │        ↓                              ↓                    │ │
│  │   [Phone-A] ←───same_device───→ [Phone-B]                │ │
│  │        │                              │                    │ │
│  │    uses_email                    uses_email               │ │
│  │        ↓                              ↓                    │ │
│  │   [Email-X] ←──similar_pattern──→ [Email-Y]              │ │
│  │                                                            │ │
│  │   Cluster Score: 0.89 (HIGH SYNTHETIC RISK)               │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 SYNTHETIC IDENTITY SIGNALS                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   SSN    │  │ Identity │  │  Credit  │  │ Bust-Out │       │
│  │ Anomaly  │  │ Velocity │  │ Behavior │  │Prediction│       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  Signal Examples:                                                │
│  • SSN issued after claimed DOB                                 │
│  • Address used by 15+ identities in 6 months                   │
│  • Credit file "thin" despite claimed age                       │
│  • Rapid credit limit increases with no payment history         │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DETECTION MODELS                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Graph   │  │Synthetic │  │ Bust-Out │  │ Identity │       │
│  │   GNN    │  │ Scorer   │  │ Predictor│  │ Resolver │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  INVESTIGATION & ACTION                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Identity │  │  SAR     │  │  Credit  │  │Consortium│       │
│  │  Review  │  │ Filing   │  │  Freeze  │  │ Sharing  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Synthetic Identity Red Flags

| Signal | Description | Risk Weight |
|--------|-------------|-------------|
| SSN-DOB Mismatch | SSN issuance year inconsistent with DOB | Critical |
| Credit File Age | File younger than identity claims | High |
| PII Velocity | Same address/phone across many applications | High |
| Authorized User Abuse | Added to multiple unrelated accounts | High |
| No Identity Footprint | No utility, rent, or employment history | Medium |
| SSN Randomization | Post-2011 randomized SSN pattern abuse | Medium |
| Bust-Out Pattern | Rapid credit usage after dormancy | Critical |

### Detection Models

| Model | Purpose | Input Features |
|-------|---------|----------------|
| Graph Neural Network | Cluster synthetic rings | Identity graph embeddings |
| Synthetic Identity Scorer | Score individual identities | PII features + graph metrics |
| Bust-Out Predictor | Predict imminent bust-out | Credit behavior sequences |
| Identity Resolver | Link fragmented identities | Fuzzy matching features |
| SSN Validator | Detect invalid/misused SSNs | SSN + DOB + issuance data |

## Directory Structure

```
fraud-detection-system/
├── src/
│   ├── ingestion/
│   │   ├── application_consumer.py    # Credit application ingestion
│   │   ├── bureau_connector.py        # Credit bureau data
│   │   ├── consortium_receiver.py     # Industry consortium data
│   │   └── dark_web_monitor.py        # Leaked credentials monitoring
│   ├── identity_elements/
│   │   ├── ssn/
│   │   │   ├── validator.py           # SSN validation rules
│   │   │   ├── issuance_checker.py    # SSN issuance year lookup
│   │   │   └── randomization.py       # Post-2011 SSN handling
│   │   ├── address/
│   │   │   ├── normalizer.py          # Address standardization
│   │   │   ├── velocity_tracker.py    # Address usage velocity
│   │   │   └── residential_scorer.py  # Residential vs commercial
│   │   ├── phone/
│   │   │   ├── carrier_lookup.py      # Carrier and line type
│   │   │   ├── voip_detector.py       # VoIP detection
│   │   │   └── velocity_tracker.py    # Phone usage velocity
│   │   ├── email/
│   │   │   ├── domain_analyzer.py     # Domain reputation
│   │   │   ├── pattern_detector.py    # Email pattern analysis
│   │   │   └── age_estimator.py       # Email account age
│   │   └── device/
│   │       ├── fingerprinter.py       # Device fingerprinting
│   │       └── binding_scorer.py      # Device-identity binding
│   ├── graph/
│   │   ├── identity_graph.py          # Neo4j graph management
│   │   ├── entity_resolution.py       # Fuzzy identity matching
│   │   ├── cluster_detector.py        # Synthetic ring detection
│   │   ├── graph_features.py          # Graph-based features
│   │   └── gnn_model.py               # Graph neural network
│   ├── detection/
│   │   ├── synthetic_scorer.py        # Synthetic identity scoring
│   │   ├── bust_out_predictor.py      # Bust-out prediction
│   │   ├── velocity_analyzer.py       # PII velocity analysis
│   │   ├── credit_behavior.py         # Credit usage patterns
│   │   ├── authorized_user.py         # AU abuse detection
│   │   └── ensemble.py                # Model ensemble
│   ├── signals/
│   │   ├── ssn_dob_mismatch.py        # SSN-DOB consistency
│   │   ├── thin_file_detector.py      # Thin credit file detection
│   │   ├── identity_age_gap.py        # Identity vs file age
│   │   ├── application_velocity.py    # Application frequency
│   │   └── address_instability.py     # Address change patterns
│   ├── investigation/
│   │   ├── case_manager.py            # Investigation workflow
│   │   ├── identity_report.py         # Identity analysis report
│   │   ├── graph_visualizer.py        # Identity graph visualization
│   │   ├── sar_generator.py           # SAR filing automation
│   │   └── consortium_reporter.py     # Consortium reporting
│   ├── api/
│   │   ├── main.py                    # FastAPI application
│   │   ├── routes/
│   │   │   ├── scoring.py             # Identity scoring endpoints
│   │   │   ├── graph.py               # Graph query endpoints
│   │   │   ├── investigation.py       # Case management
│   │   │   └── consortium.py          # Data sharing endpoints
│   │   └── websocket.py               # Real-time alerts
│   ├── monitoring/
│   │   ├── metrics.py                 # Detection metrics
│   │   ├── model_performance.py       # Model monitoring
│   │   └── bust_out_tracker.py        # Bust-out monitoring
│   └── config/
│       └── settings.py
├── models/
│   ├── synthetic_scorer/
│   ├── bust_out/
│   └── gnn/
├── data/
│   ├── ssn_issuance/                  # SSN issuance reference
│   └── address_reference/             # Address validation data
├── scripts/
│   ├── train_synthetic_scorer.py
│   ├── train_bust_out_model.py
│   ├── build_identity_graph.py
│   ├── evaluate_detection.py
│   └── generate_synthetic_data.py
├── notebooks/
│   ├── 01_identity_graph_eda.ipynb
│   ├── 02_synthetic_patterns.ipynb
│   ├── 03_bust_out_analysis.ipynb
│   └── 04_model_evaluation.ipynb
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
└── README.md
```

## Commands

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start infrastructure (Neo4j, Kafka, PostgreSQL)
docker-compose up -d neo4j kafka postgres redis
```

### Building Identity Graph

```bash
# Initialize identity graph
python scripts/build_identity_graph.py \
    --applications data/applications.parquet \
    --bureau-data data/bureau_snapshots.parquet

# Run entity resolution
python scripts/build_identity_graph.py \
    --mode entity-resolution \
    --similarity-threshold 0.85

# Detect synthetic clusters
python scripts/build_identity_graph.py \
    --mode cluster-detection \
    --min-cluster-size 3
```

### Training Models

```bash
# Train synthetic identity scorer
python scripts/train_synthetic_scorer.py \
    --data data/training/labeled_identities.parquet \
    --graph-features data/features/graph_embeddings.parquet \
    --output models/synthetic_scorer/v1

# Train bust-out predictor
python scripts/train_bust_out_model.py \
    --data data/training/credit_sequences.parquet \
    --lookback-months 12 \
    --output models/bust_out/v1

# Train Graph Neural Network
python scripts/train_gnn.py \
    --graph neo4j://localhost:7687 \
    --output models/gnn/v1 \
    --epochs 100
```

### Running the System

```bash
# Start API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Start real-time scoring consumer
python -m src.ingestion.application_consumer

# Full stack with Docker
docker-compose up -d
```

### API Usage

```bash
# Score an identity for synthetic risk
curl -X POST http://localhost:8000/api/v1/score/synthetic \
  -H "Content-Type: application/json" \
  -d '{
    "ssn_last4": "1234",
    "ssn_first5": "12345",
    "dob": "1985-03-15",
    "first_name": "John",
    "last_name": "Smith",
    "address": {
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "zip": "90210"
    },
    "phone": "555-123-4567",
    "email": "john.smith@email.com",
    "application_date": "2024-01-15"
  }'

# Get identity graph for investigation
curl "http://localhost:8000/api/v1/graph/identity/ssn-hash-abc123?depth=2"

# Predict bust-out risk for existing account
curl -X POST http://localhost:8000/api/v1/score/bust-out \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "acct_123",
    "include_credit_behavior": true
  }'

# Get synthetic cluster members
curl "http://localhost:8000/api/v1/clusters/cluster_456/members"
```

## Configuration

```yaml
# config/settings.yaml
scoring:
  synthetic_identity:
    model_weights:
      ssn_signals: 0.25
      graph_features: 0.30
      velocity_signals: 0.20
      credit_behavior: 0.15
      device_binding: 0.10

    thresholds:
      high_risk: 0.80
      medium_risk: 0.50
      review: 0.30

  bust_out:
    lookback_months: 12
    prediction_window_days: 90
    threshold: 0.75

identity_graph:
  neo4j:
    uri: bolt://localhost:7687
    user: neo4j
    password: ${NEO4J_PASSWORD}

  entity_resolution:
    ssn_weight: 1.0
    name_weight: 0.3
    address_weight: 0.4
    phone_weight: 0.3
    email_weight: 0.2
    similarity_threshold: 0.85

  cluster_detection:
    algorithm: louvain
    min_cluster_size: 3
    resolution: 1.0

signals:
  ssn_issuance:
    # SSN Area Number to year mapping
    lookup_table: data/ssn_issuance/area_year_mapping.csv
    randomization_start: "2011-06-25"

  velocity:
    address_max_identities_6mo: 5
    phone_max_identities_6mo: 3
    email_max_identities_6mo: 2

  credit_file:
    min_age_years: 3  # For claimed age > 21
    thin_file_tradelines: 3

consortium:
  enabled: true
  provider: early_warning
  share_synthetic_flags: true
  receive_bust_out_alerts: true

kafka:
  bootstrap_servers: localhost:9092
  topics:
    applications: credit-applications
    scores: synthetic-scores
    alerts: bust-out-alerts
```

### Signal Rules

```yaml
# signals/ssn_rules.yaml
signals:
  - name: ssn_dob_mismatch
    description: SSN issuance year inconsistent with DOB
    severity: critical
    logic: |
      ssn_issuance_year > dob_year + 1
      AND ssn_issuance_year != RANDOMIZED_ERA
    score_impact: 0.40

  - name: ssn_death_master_match
    description: SSN appears in Death Master File
    severity: critical
    logic: ssn IN death_master_file
    score_impact: 0.50

  - name: ssn_itin_pattern
    description: SSN matches ITIN pattern (9XX-XX-XXXX)
    severity: high
    logic: ssn_area BETWEEN 900 AND 999
    score_impact: 0.35

  - name: multiple_ssns_same_identity
    description: Multiple SSNs linked to same name+DOB
    severity: high
    logic: |
      COUNT(DISTINCT ssn) > 1
      WHERE name_dob_match
    score_impact: 0.45
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/score/synthetic` | POST | Score identity for synthetic risk |
| `/api/v1/score/bust-out` | POST | Predict bust-out risk |
| `/api/v1/score/application` | POST | Full application scoring |
| `/api/v1/graph/identity/{id}` | GET | Get identity graph |
| `/api/v1/graph/cluster/{id}` | GET | Get synthetic cluster |
| `/api/v1/clusters` | GET | List detected clusters |
| `/api/v1/signals/{identity_id}` | GET | Get triggered signals |
| `/api/v1/investigation/cases` | GET, POST | Manage cases |
| `/api/v1/consortium/share` | POST | Share to consortium |
| `/ws/alerts` | WebSocket | Real-time bust-out alerts |

## Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Synthetic Detection Rate | % of synthetic identities caught | > 85% |
| False Positive Rate | % of real identities flagged | < 2% |
| Bust-Out Prediction Accuracy | Correct predictions in 90-day window | > 75% |
| Detection Lead Time | Days before bust-out | > 30 days |
| Cluster Purity | % of cluster members that are synthetic | > 90% |
| Graph Entity Resolution F1 | Entity matching accuracy | > 0.92 |

## Implementation Phases

### Phase 1: Identity Graph
- [ ] Neo4j graph schema
- [ ] Entity resolution pipeline
- [ ] Basic graph queries
- [ ] Cluster detection

### Phase 2: Synthetic Signals
- [ ] SSN validation and issuance checking
- [ ] PII velocity tracking
- [ ] Credit file age analysis
- [ ] Device fingerprinting

### Phase 3: ML Models
- [ ] Synthetic identity scorer
- [ ] Graph Neural Network
- [ ] Bust-out predictor
- [ ] Model ensemble

### Phase 4: Investigation Tools
- [ ] Case management
- [ ] Graph visualization
- [ ] SAR automation
- [ ] Consortium integration

### Phase 5: Production
- [ ] Real-time scoring pipeline
- [ ] Monitoring and alerting
- [ ] A/B testing framework
- [ ] Feedback loop

## Dependencies

```
# Core
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.6.0

# Graph
neo4j>=5.15.0
networkx>=3.2.0
torch-geometric>=2.4.0

# ML
scikit-learn>=1.4.0
xgboost>=2.0.0
torch>=2.2.0

# Data
pandas>=2.2.0
numpy>=1.26.0
pyarrow>=15.0.0

# Streaming
kafka-python>=2.0.0
redis>=5.0.0

# Entity Resolution
recordlinkage>=0.16
jellyfish>=1.0.0  # String similarity

# Monitoring
prometheus-client>=0.19.0
```

## Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires Neo4j)
pytest tests/integration -v

# Test synthetic detection
pytest tests/detection -v

# Test with synthetic fraud scenarios
python scripts/generate_synthetic_data.py --scenarios bust_out,ring_fraud
pytest tests/scenarios -v
```
