# App Gradio : visualisation et annotation

Interface pour parcourir les contributions commune par commune (texte extrait + PDF source)
et activer deux variables par contribution : **Anonymisé** et **Contribution d'intérêt**.

## Fonctionnement

Les données sont lues **directement dans la base PostgreSQL**, pas de fichier intermédiaire.
Une contribution affiche : ses thèmes (instances `topic` reliées au référentiel
`ref_topic`, avec verbatim et résumé quand l'analyse existe), ses sentiments (`feeling`),
le texte de sa dernière extraction (`extraction`, `max(id)`), et son PDF (`data/raw/pdfs/`). Les deux
cases cochées sont écrites dans la table `annotation` (UPSERT ; les deux décochées = ligne
supprimée). Voir `database/README.md` pour le modèle.

| Fichier | Rôle |
|---|---|
| `app.py` | interface Gradio : mise en page, navigation, événements |
| `data_helpers.py` | requêtes SQL (SQLAlchemy + pandas) et sauvegarde des annotations |

## Prérequis

1. Base accessible et remplie — via `uv run python -m database.seed_mock` (démo) ou le pipeline data.
2. `.env` renseigné : `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (mêmes variables que `database/db.py`).
3. Les PDF présents dans `data/raw/pdfs/` pour l'aperçu (sinon « PDF introuvable » s'affiche, le reste marche).

## Lancer

```bash
uv run python gradio_app/app.py # http://localhost:7860
```
