"""Repository paths."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
CURATED_DIR = DATA_DIR / "curated"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_CSV = DATA_DIR / "manifest.csv"
CACHE_DIR = ROOT / "cache"
