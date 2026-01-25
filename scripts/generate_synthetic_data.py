#!/usr/bin/env python3
"""Generate synthetic test data for development."""

import argparse
import logging
import random
import string
import hashlib
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_ssn_hash():
    """Generate a fake SSN hash."""
    ssn = f"{random.randint(100, 899):03d}-{random.randint(10, 99):02d}-{random.randint(1000, 9999):04d}"
    return hashlib.sha256(ssn.encode()).hexdigest()


def generate_identity(is_synthetic: bool = False):
    """Generate a single identity record."""
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "James", "Jessica"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]

    identity = {
        "identity_id": f"ID-{hashlib.md5(str(random.random()).encode()).hexdigest()[:12]}",
        "ssn_hash": generate_ssn_hash(),
        "first_name": random.choice(first_names),
        "last_name": random.choice(last_names),
        "dob": (datetime.now() - timedelta(days=random.randint(7300, 25000))).date(),
        "address_hash": hashlib.md5(str(random.random()).encode()).hexdigest()[:16],
        "phone_hash": hashlib.md5(str(random.random()).encode()).hexdigest()[:16],
        "email_hash": hashlib.md5(str(random.random()).encode()).hexdigest()[:16],
        "is_synthetic": is_synthetic,
    }

    # Add synthetic identity characteristics
    if is_synthetic:
        # Thin file
        identity["num_tradelines"] = random.randint(0, 2)
        identity["file_age_months"] = random.randint(1, 18)
        identity["au_accounts"] = random.randint(2, 6)
    else:
        identity["num_tradelines"] = random.randint(3, 15)
        identity["file_age_months"] = random.randint(24, 300)
        identity["au_accounts"] = random.randint(0, 2)

    return identity


def generate_synthetic_ring(ring_size: int = 5):
    """Generate a ring of synthetic identities sharing elements."""
    # Shared elements
    shared_address = hashlib.md5(str(random.random()).encode()).hexdigest()[:16]
    shared_phone = hashlib.md5(str(random.random()).encode()).hexdigest()[:16]

    identities = []
    for i in range(ring_size):
        identity = generate_identity(is_synthetic=True)
        # Share some elements
        if random.random() < 0.7:
            identity["address_hash"] = shared_address
        if random.random() < 0.5:
            identity["phone_hash"] = shared_phone
        identities.append(identity)

    return identities


def generate_bust_out_sequence(is_bust_out: bool = False):
    """Generate credit behavior sequence."""
    months = 12

    if is_bust_out:
        # Bust-out pattern: increasing balances, decreasing payments
        balances = [1000 + i * 500 + random.randint(-100, 100) for i in range(months)]
        payments = [500 - i * 30 + random.randint(-50, 50) for i in range(months)]
        utilization = [min(0.99, 0.3 + i * 0.06) for i in range(months)]
        cash_advances = [0] * 8 + [random.randint(500, 2000) for _ in range(4)]
    else:
        # Normal pattern
        balances = [random.randint(500, 3000) for _ in range(months)]
        payments = [random.randint(200, 800) for _ in range(months)]
        utilization = [random.uniform(0.2, 0.6) for _ in range(months)]
        cash_advances = [0] * months

    return {
        "account_id": f"ACCT-{random.randint(100000, 999999)}",
        "monthly_balances": balances,
        "monthly_payments": payments,
        "utilization_rates": utilization,
        "cash_advance_amounts": cash_advances,
        "months_on_books": random.randint(6, 36),
        "is_bust_out": is_bust_out,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--num-identities", type=int, default=1000)
    parser.add_argument("--synthetic-ratio", type=float, default=0.1)
    parser.add_argument("--num-rings", type=int, default=10)
    parser.add_argument("--scenarios", nargs="+",
                       choices=["identities", "bust_out", "ring_fraud"],
                       default=["identities"])
    args = parser.parse_args()

    import os
    os.makedirs(args.output, exist_ok=True)

    if "identities" in args.scenarios:
        logger.info(f"Generating {args.num_identities} identities...")
        identities = []

        # Regular identities
        num_legitimate = int(args.num_identities * (1 - args.synthetic_ratio))
        for _ in range(num_legitimate):
            identities.append(generate_identity(is_synthetic=False))

        # Synthetic identities
        num_synthetic = args.num_identities - num_legitimate
        for _ in range(num_synthetic):
            identities.append(generate_identity(is_synthetic=True))

        df = pd.DataFrame(identities)
        output_path = f"{args.output}/identities.parquet"
        df.to_parquet(output_path)
        logger.info(f"Saved {len(df)} identities to {output_path}")

    if "ring_fraud" in args.scenarios:
        logger.info(f"Generating {args.num_rings} synthetic rings...")
        all_ring_identities = []
        for _ in range(args.num_rings):
            ring = generate_synthetic_ring(ring_size=random.randint(3, 8))
            all_ring_identities.extend(ring)

        df = pd.DataFrame(all_ring_identities)
        output_path = f"{args.output}/ring_fraud_identities.parquet"
        df.to_parquet(output_path)
        logger.info(f"Saved {len(df)} ring identities to {output_path}")

    if "bust_out" in args.scenarios:
        logger.info("Generating bust-out sequences...")
        sequences = []

        for _ in range(800):
            sequences.append(generate_bust_out_sequence(is_bust_out=False))
        for _ in range(200):
            sequences.append(generate_bust_out_sequence(is_bust_out=True))

        df = pd.DataFrame(sequences)
        output_path = f"{args.output}/credit_sequences.parquet"
        df.to_parquet(output_path)
        logger.info(f"Saved {len(df)} sequences to {output_path}")


if __name__ == "__main__":
    main()
