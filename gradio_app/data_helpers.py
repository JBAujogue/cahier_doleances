import json
from pathlib import Path
import pandas as pd

# Constantes
ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "pdfs"
DATA_FILE = ROOT / "data" / "processed" / "contributions.csv"
VALIDATIONS_FILE = ROOT / "data" / "processed" / "validations.json"

df = pd.read_csv(DATA_FILE)

def list_communes() -> list[str]:
    communes = df[["insee", "commune"]].drop_duplicates().sort_values("commune")
    # insee dans le libellé pour distinguer les communes homonymes (ex. Fontcouverte)
    return [f"{c} ({i})" for i, c in zip(communes["insee"], communes["commune"])]

def _rows(commune: str) -> pd.DataFrame:
    """Les contributions d'une commune (à partir du libellé '... (insee)')."""
    insee = int(commune.split("(")[-1].strip(") "))
    return df[df["insee"] == insee].reset_index(drop=True)

def _int(value) -> str:
    """Entier en texte, ou 'N/C' si manquant."""
    return "N/C" if pd.isna(value) else str(int(value))

def list_contributions(commune: str) -> list[str]:
    rows = _rows(commune)
    return [f"{i + 1}/{len(rows)} | {t}" for i, t in enumerate(rows["type"])]

def get_contribution(commune: str, idx: int) -> dict:
    rows = _rows(commune)
    r = rows.iloc[idx]
    n = len(rows)
    auteur = r["auteur"] if pd.notna(r["auteur"]) else "N/C"
    return {
        "meta": (
            f"### {r['commune']}\n"
            f"- INSEE : {r['insee']}\n"
            f"- Intercommunalité : {r['intercommunalite']}\n"
            f"- Habitants : {r['habitants']}\n"
            f"- Contributions : {n}"
        ),
        "header": (
            f"#### Contribution {idx + 1}/{n}\n\n"
            f"| Nature | Auteur | Pages | Lignes | Mots |\n"
            f"|---|---|---|---|---|\n"
            f"| {r['type']} | {auteur} | {_int(r['nb_pages'])} "
            f"| {_int(r['nb_lignes'])} | {_int(r['nb_mots'])} |"
        ),
        "text": r["text"],
        "pdf_file": r["pdf_file"],
    }

def save_decision(commune: str, idx: int, decision: str, note: str) -> str:
    data = json.loads(VALIDATIONS_FILE.read_text()) if VALIDATIONS_FILE.exists() else {}
    data[_rows(commune).iloc[idx]["id"]] = {"decision": decision, "note": note}
    VALIDATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return f"Enregistré : {decision} (contribution {idx + 1})."
