import re
import pandas as pd

AUTEURS = ["couple", "collectif", "association", "homme", "femme"]


def clean_communes(meta: pd.DataFrame) -> pd.DataFrame:
    """Métadonnées par commune, avec un pdf_file propre (1er fichier)."""
    data_commune = meta[
        ["insee", "intercommunalite", "commune", "habitants", "pdf_file"]
    ].copy()
    data_commune["pdf_file"] = data_commune["pdf_file"].apply(
        lambda files: files[0] if isinstance(files, list) and files else files
    )
    return data_commune


def structure_contributions(extraction: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """1 ligne = 1 contribution, rattachée à son insee par index.

    (extraction et meta sont alignés : même ordre, 125 lignes)
    """
    extraction = extraction.copy()
    extraction["pdf_files"] = extraction["pdf_files"].apply(
        lambda x: x[0] if isinstance(x, list) else x
    )
    # on ne garde que le nom du fichier (on retire le dossier en préfixe)
    extraction["pdf_files"] = extraction["pdf_files"].str.replace(r"^.*/", "", regex=True)
    extraction = extraction.reset_index(drop=True)
    meta = meta.reset_index(drop=True)

    rows = []
    for i, contribs in extraction["contributions"].items():
        if not contribs:
            continue
        df = pd.DataFrame(contribs)
        df["insee"] = meta.loc[i, "insee"]
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def parse(s):
    s = str(s)
    typ = re.split(r"\s*\(|,", re.sub(r"^\s*[A-Za-z]*\d+\.\s*", "", s))[0].strip()
    num = re.match(r"\s*(\d+)\s*\.", s)
    pg = re.search(r"(\d+)\s*pages?", s)
    lg = re.search(r"((?:\d+\s*\+\s*)*\d+)\s*lignes?", s)
    mt = re.search(r"(\d+)\s*mots", s)
    aut = next((a for a in AUTEURS if re.search(rf"\b{a}\b", s, re.I)), pd.NA)
    return pd.Series(
        {
            "num": int(num.group(1)) if num else pd.NA,
            "type": typ,
            "nb_pages": int(pg.group(1)) if pg else pd.NA,
            "nb_lignes": sum(map(int, re.findall(r"\d+", lg.group(1)))) if lg else pd.NA,
            "nb_mots": int(mt.group(1)) if mt else pd.NA,
            "auteur": aut,
        }
    )


def parse_titles(data_contribs: pd.DataFrame) -> pd.DataFrame:
    """Ajoute num/type/dimensions/auteur depuis le titre, puis retire le titre."""
    cols = ["num", "type", "nb_pages", "nb_lignes", "nb_mots", "auteur"]
    data_contribs[cols] = data_contribs["title"].apply(parse)
    data_contribs[["num", "nb_pages", "nb_lignes", "nb_mots"]] = data_contribs[
        ["num", "nb_pages", "nb_lignes", "nb_mots"]
    ].astype("Int64")
    return data_contribs.drop(columns="title")


def merge_communes(data_contribs: pd.DataFrame, data_commune: pd.DataFrame) -> pd.DataFrame:
    """Vue complète : contributions + métadonnées commune, jointes sur insee."""
    return data_contribs.merge(data_commune, on="insee", how="left")


def add_id(data_full: pd.DataFrame) -> pd.DataFrame:
    """Identifiant propre : contrib_<insee>_<n>, n démarrant à 1 par commune."""
    data_full = data_full.copy()
    n = data_full.groupby("insee").cumcount() + 1
    data_full.insert(0, "id", "contrib_" + data_full["insee"].astype(str) + "_" + n.astype(str))
    return data_full
