# Pipeline

Transforme les données brutes des cahiers en un fichier propre.

Ce que fait le code (3 étapes) :

1. Load : lit les JSON dans data/raw/
2. Validate : vérifie que les colonnes attendues sont là
3. Transform : nettoie, structure (1 ligne = 1 contribution), parse les titres, joint sur insee

Sortie : data/processed/contributions.csv

Attention : les données brutes ne sont pas dans le repo (sous NDA). Avant de
lancer, récupère les fichiers sources auprès de l'équipe et mets-les dans data/raw/.

## Lancer

```
uv run python data_pipeline/pipeline.py
```
