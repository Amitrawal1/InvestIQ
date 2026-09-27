"""Settings shared by the XBRL financials collector, parser and validator."""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent

# Raw downloads (git-ignored via ml/data/raw/)
SAMPLE_DIR = ML_DIR / "data" / "raw" / "xbrl_samples"
XBRL_CACHE_DIR = ML_DIR / "data" / "raw" / "xbrl"

# Small and mid caps across sectors, plus two lenders (UJJIVANSFB, CREDITACC)
# whose XBRL uses the banking/NBFC format
SAMPLE_SYMBOLS = [
    "KAYNES", "ZENSARTECH", "MTARTECH", "KPITTECH", "HAPPSTMNDS", "DIXON", "TANLA",
    "ROUTE", "NEWGEN", "CAMS", "AMBER", "SAFARI", "BIKAJI", "VGUARD", "GRINDWELL",
    "SOBHA", "ASTRAL", "DEEPAKNTR", "JKLAKSHMI", "CERA", "UJJIVANSFB", "CREDITACC",
]
