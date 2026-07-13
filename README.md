# Cahiers de doléances

Projet Data For Good : outil de visualisation et d'annotation des cahiers de doléances.
Les contributions extraites des PDF sont stockées en base PostgreSQL ; une app Gradio permet
de les parcourir commune par commune et de les annoter (anonymisé, contribution d'intérêt).

## Organisation

- `database/` : le modèle de données et les migrations qui structurent la base PostgreSQL | [documentation](database/README.md)
- `gradio_app/` : l'interface pour parcourir les contributions et les annoter | [documentation](gradio_app/README.md)

## Installation

Ce projet utilise [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances Python
(prérequis). Une fois uv installé :

```bash
uv sync
```

Cela installe la bonne version de Python, crée l'environnement virtuel et installe les
dépendances. Sous VSCode l'environnement s'active automatiquement ; sinon :

```bash
source .venv/bin/activate
```

Ou préfixez vos commandes par `uv run` :

```bash
uv run python -m database.seed_mock  # remplit la base avec le seed de démo
uv run python gradio_app/app.py      # lance l'app
```

## Base de données

La connexion PostgreSQL est lue depuis `.env` (`DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD`, `DB_NAME`). Voir [database/README.md](database/README.md) pour le modèle,
les migrations Alembic et le seed.

## Lancer les pre-commit hooks localement

[Installer pre-commit](https://pre-commit.com/) puis :

```bash
pre-commit run --all-files
```

## Tester avec Tox

```bash
tox -vv
```
