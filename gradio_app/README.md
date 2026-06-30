# App Gradio

Interface pour parcourir les contributions commune par commune (texte + PDF)
et décider de garder ou rejeter chacune.

Lit les données produites par le pipeline : data/processed/contributions.csv

Deux fichiers :

- app.py : l'interface Gradio (mise en page, navigation)
- data_helpers.py : lecture des données (communes, contributions, PDF) et sauvegarde des décisions

## Lancer

Le pipeline doit avoir été lancé avant (pour produire le fichier de données).

```
uv run python gradio_app/app.py
```
