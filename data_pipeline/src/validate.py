import pandas as pd

META_COLUMNS = ["insee", "intercommunalite", "commune", "habitants", "pdf_file"]
EXTRACTION_COLUMNS = ["pdf_files", "contributions"]


def check_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    """Lève une erreur si des colonnes attendues manquent dans `df`."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} : colonnes manquantes {missing} (présentes : {list(df.columns)})")
