# Synthetic Identity Fraud Detection System

A specialized fraud detection platform focused on detecting synthetic identities—fabricated personas combining real and fake PII elements that are built up over time before "busting out."

## Features

- **Graph-based Identity Resolution**: Links SSN, address, phone, and email clusters using Neo4j
- **PII Velocity Analysis**: Tracks how fast identity elements spread across applications
- **Synthetic Identity Scoring**: ML-based scoring using cross-institution data patterns
- **Bust-out Prediction**: Predicts imminent bust-out before it happens
- **Real-time Detection**: Kafka-based streaming for real-time application scoring
- **Investigation Tools**: Case management, graph visualization, and SAR generation

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Neo4j 5.x
- Apache Kafka

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/fraud-detection-system.git
cd fraud-detection-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration
```

### Start Infrastructure

```bash
# Start all services with Docker Compose
docker-compose -f docker/docker-compose.yml up -d

# Or start individual services
docker-compose -f docker/docker-compose.yml up -d neo4j kafka postgres redis
```

### Run the API

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
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
    "address": {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "90210"},
    "phone": "555-123-4567",
    "email": "john.smith@email.com",
    "application_date": "2024-01-15"
  }'
```

## Project Structure

```
fraud-detection-system/
├── src/
│   ├── ingestion/          # Data ingestion (Kafka, bureau, consortium)
│   ├── identity_elements/  # PII analysis (SSN, address, phone, email, device)
│   ├── graph/              # Neo4j identity graph and GNN models
│   ├── detection/          # Detection models (synthetic, bust-out, ensemble)
│   ├── signals/            # Signal detectors (SSN-DOB mismatch, velocity, etc.)
│   ├── investigation/      # Case management and SAR generation
│   ├── api/                # FastAPI application
│   └── monitoring/         # Metrics and model monitoring
├── models/                 # Trained model files
├── data/                   # Reference data
├── scripts/                # Training and utility scripts
├── tests/                  # Test suite
└── docker/                 # Docker configuration
```

## Training Models

```bash
# Generate synthetic training data
python scripts/generate_synthetic_data.py --output data/training --scenarios identities bust_out

# Train synthetic scorer
python scripts/train_synthetic_scorer.py \
  --data data/training/identities.parquet \
  --output models/synthetic_scorer/v1/model.joblib

# Train bust-out predictor
python scripts/train_bust_out_model.py \
  --data data/training/credit_sequences.parquet \
  --output models/bust_out/v1/model.joblib
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_synthetic_scorer.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation, API reference, and configuration options.

## License

Proprietary - All rights reserved
