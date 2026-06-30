# Cahiers de doléances

Analyse des cahiers de doléances (projet Data For Good).
Un pipeline prépare les données, une app Gradio sert à sélectionner les contributions.

## Organisation

- `data_pipeline/` : prépare les données pour voir [data_pipeline/README.md](data_pipeline/README.md)
- `gradio_app/` : interface de sélection des contributions pour voir [gradio_app/README.md](gradio_app/README.md)
- `data/` : les données (non versionnées, sous NDA)

# Contributing


## Installation

- [Installation de Python](#installation-de-python)

Ce projet utilise [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances Python. Il est préréquis pour l'installation de ce projet.

Une fois installé, il suffit de lancer la commande suivante pour installer la version de Python adéquate, créer un environnement virtuel et installer les dépendances du projet.

```bash
uv sync
```

A l'usage, si vous utilisez VSCode, l'environnement virtuel sera automatiquement activé lorsque vous ouvrirez le projet. Sinon, il suffit de l'activer manuellement avec la commande suivante :

```bash
source .venv/bin/activate
```

Ou alors, utilisez la commande `uv run ...` (au lieu de `python ...`) pour lancer un script Python. Par exemple:

```bash
uv run python data_pipeline/pipeline.py # prépare les données
uv run python gradio_app/app.py # lance l'app
```


## Lancer les precommit-hook localement

[Installer les precommit](https://pre-commit.com/)

    pre-commit run --all-files

## Utiliser Tox pour tester votre code

    tox -vv
