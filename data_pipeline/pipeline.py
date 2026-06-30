from pathlib import Path
from src.load import load_extraction, load_meta
from src.logger import get_logger
from src.transform import (
    add_id, clean_communes,merge_communes,
    parse_titles,structure_contributions,
)
from src.validate import EXTRACTION_COLUMNS, META_COLUMNS, check_columns

# Constantes
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
META_FILE = RAW_DIR / "meta.json"
EXTRACTION_FILE = RAW_DIR / "extraction.json"
OUTPUT_FILE = PROCESSED_DIR / "contributions.csv"

log = get_logger()

def build():
    # 1. Load
    log.info("Load")
    meta = load_meta(META_FILE)
    extraction = load_extraction(EXTRACTION_FILE)
    log.info("meta=%d communes · extraction=%d lignes", len(meta), len(extraction))

    # 2. Validate
    log.info("Validate")
    check_columns(meta, META_COLUMNS, "meta")
    check_columns(extraction, EXTRACTION_COLUMNS, "extraction")
    log.info("colonnes OK")

    # 3. Transform
    log.info("Transform")
    data_commune = clean_communes(meta)
    data_contribs = parse_titles(structure_contributions(extraction, meta))
    data_full = add_id(merge_communes(data_contribs, data_commune))
    log.info(
        "%d contributions et %d communes", len(data_full), data_full["insee"].nunique()
    )
    return data_full


def main() -> None:
    log.info("Démarrage du pipeline")
    data_full = build()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    data_full.to_csv(OUTPUT_FILE, index=False)
    log.info("Écrit → %s (%d lignes)", OUTPUT_FILE.relative_to(ROOT), len(data_full))


if __name__ == "__main__":
    main()
