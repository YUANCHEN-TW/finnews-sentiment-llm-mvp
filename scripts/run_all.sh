#!/usr/bin/env bash
set -e
python src/etl/demo_seed.py
python src/models/train_baseline.py
uvicorn src.app.main:app --reload
