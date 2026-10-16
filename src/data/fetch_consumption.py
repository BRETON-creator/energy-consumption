"""Télécharge les données nationales eCO2mix (RTE) depuis l'API Open Data ODRÉ.

Combine l'historique consolidé/définitif et les données temps réel récentes,
puis sauvegarde le résultat brut dans data/raw/eco2mix_national.parquet.

Usage :
    uv run python -m src.data.fetch_consumption
"""

import io
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets"
DATASETS = [
    "eco2mix-national-cons-def",  # historique depuis 2012 (consolidé puis définitif)
    "eco2mix-national-tr",  # temps réel, ~45 derniers jours
]
TEXT_COLUMNS = ["perimetre", "nature", "date", "heure"]
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "eco2mix_national.parquet"

log = logging.getLogger(__name__)


def fetch_dataset(
    dataset: str,
    select: list[str] | None = None,
    where: str | None = None,
) -> pd.DataFrame:
    """Télécharge un dataset via l'endpoint d'export parquet, filtré côté serveur si demandé.

    Args:
        dataset: identifiant du dataset ODRÉ, ex. "eco2mix-national-cons-def".
        select: colonnes à récupérer (toutes par défaut). Doit inclure "date_heure".
        where: filtre ODSQL, ex. "date_heure >= date'2020-01-01' and consommation is not null".
    """
    url = f"{BASE_URL}/{dataset}/exports/parquet"
    params = {}
    if select is not None:
        params["select"] = ",".join(select)
    if where is not None:
        params["where"] = where
    log.info(f"Téléchargement de {dataset}... {params or ''}")
    try:
        response = requests.get(url, params=params, timeout=300)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Échec du téléchargement de {dataset} : {e}")
        raise
    df = pd.read_parquet(io.BytesIO(response.content))
    df["date_heure"] = pd.to_datetime(df["date_heure"], utc=True)
    # Certaines colonnes de mesure sont typées texte dans l'API : on force le numérique.
    measures = df.columns.difference(TEXT_COLUMNS + ["date_heure"])
    df[measures] = df[measures].apply(pd.to_numeric, errors="coerce")
    log.info(f"{dataset} : {len(df):,} lignes, de {df['date_heure'].min()} à {df['date_heure'].max()}")
    return df


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    frames = [fetch_dataset(name) for name in DATASETS]
    # En cas de recouvrement, on garde les données consolidées (premier dataset).
    df = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="date_heure", keep="first")
        .sort_values("date_heure")
        .set_index("date_heure")
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH)

    observed = df["consommation"].dropna()
    log.info(f"Sauvegardé : {OUTPUT_PATH}")
    log.info(f"{len(df):,} lignes au total, dont {len(observed):,} avec une consommation observée")
    log.info(f"Consommation observée de {observed.index.min()} à {observed.index.max()}")


if __name__ == "__main__":
    main()
