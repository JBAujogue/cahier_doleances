import pandas as pd

def load_meta(path) -> pd.DataFrame:
    """Métadonnées des communes (JSON brut)."""
    return pd.read_json(path)


def load_extraction(path) -> pd.DataFrame:
    """Contributions extraites (JSON brut)."""
    return pd.read_json(path)
