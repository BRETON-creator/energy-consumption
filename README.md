# Prévision de la consommation électrique française

Prévision de la demande d'électricité en France (données RTE eCO2mix) avec des modèles de ML et de deep learning.

## Installation

```bash
uv sync
```

## Données

```bash
uv run python -m src.data.fetch_consumption
uv run python -m src.data.fetch_meteo
```

Télécharge l'historique national eCO2mix (2012 → aujourd'hui) depuis l'API [ODRÉ](https://odre.opendatasoft.com) vers `data/raw/eco2mix_national.parquet`.

## Exploration

```bash
uv run jupyter lab notebooks/exploration.ipynb
```

Analyse la série et justifie les choix de préparation ; écrit `data/processed/consommation_horaire.parquet`.

## Structure

```
data/raw/        données brutes téléchargées (non versionnées)
data/processed/  données préparées pour la modélisation
notebooks/       exploration
src/data/        scripts de téléchargement (consommation RTE, météo Open-Meteo)
```
