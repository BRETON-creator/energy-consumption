"""Télécharge les températures horaires historiques depuis l'API Open-Meteo (réanalyse ERA5).

Une série par grande ville, puis une température « France » pondérée par la population,
la consommation électrique étant surtout sensible à la température là où vivent les gens.

Usage :
    uv run python -m src.data.fetch_meteo
"""

import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
# Ville : (latitude, longitude, poids ≈ population de l'aire urbaine en millions, à affiner)
CITIES = {
    "Paris": (48.86, 2.35, 13.1),
    "Lyon": (45.76, 4.84, 2.3),
    "Marseille": (43.30, 5.37, 1.9),
    "Lille": (50.63, 3.06, 1.5),
    "Toulouse": (43.60, 1.44, 1.5),
    "Bordeaux": (44.84, -0.58, 1.4),
    "Nantes": (47.22, -1.55, 1.0),
    "Nice": (43.70, 7.27, 1.0),
    "Strasbourg": (48.57, 7.75, 0.8),
    "Rennes": (48.11, -1.68, 0.8),
}
ARCHIVE_DELAY_DAYS = 5  # l'archive ERA5 est publiée avec quelques jours de retard
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "meteo_villes.parquet"

log = logging.getLogger(__name__)


def _get(params: dict, retries: int = 3) -> dict | list:
    """Appel à l'API avec nouvel essai en cas de dépassement du quota par minute (HTTP 429)."""
    for attempt in range(retries):
        response = requests.get(ARCHIVE_URL, params=params, timeout=120)
        if response.status_code == 429 and attempt < retries - 1:
            log.warning("Quota Open-Meteo atteint, nouvel essai dans 60 s...")
            time.sleep(60)
            continue
        response.raise_for_status()
        return response.json()


def fetch_temperatures(start: str, end: str, cities: dict = CITIES) -> pd.DataFrame:
    """Températures horaires à 2 m (°C) entre deux dates incluses (AAAA-MM-JJ).

    Retourne un DataFrame indexé en UTC, avec une colonne par ville.
    """
    names = list(cities)
    params = {
        "latitude": ",".join(str(cities[n][0]) for n in names),
        "longitude": ",".join(str(cities[n][1]) for n in names),
        "start_date": start,
        "end_date": end,
        "hourly": "temperature_2m",
        "timezone": "GMT",
    }
    data = _get(params)
    if isinstance(data, dict):  # l'API renvoie un objet (et non une liste) pour une seule ville
        data = [data]
    return pd.DataFrame({
        name: pd.Series(
            loc["hourly"]["temperature_2m"],
            index=pd.to_datetime(loc["hourly"]["time"], utc=True),
        )
        for name, loc in zip(names, data)
    }).rename_axis("date_heure")


def fetch_history(start: str, end: str, cities: dict = CITIES) -> pd.DataFrame:
    """Comme fetch_temperatures, mais découpé par année pour rester sous les quotas de l'API."""
    frames = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        chunk_start = max(start, f"{year}-01-01")
        chunk_end = min(end, f"{year}-12-31")
        log.info(f"Téléchargement {chunk_start} → {chunk_end}...")
        frames.append(fetch_temperatures(chunk_start, chunk_end, cities))
    return pd.concat(frames)


def national_temperature(temperatures: pd.DataFrame, cities: dict = CITIES) -> pd.Series:
    """Température France : moyenne des villes pondérée par leur population."""
    weights = pd.Series({name: cities[name][2] for name in temperatures.columns})
    return (temperatures * weights).sum(axis=1) / weights.sum()


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    end = (date.today() - timedelta(days=ARCHIVE_DELAY_DAYS)).isoformat()
    df = fetch_history("2012-01-01", end)
    df["France"] = national_temperature(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH)
    log.info(f"Sauvegardé : {OUTPUT_PATH} ({len(df):,} heures, de {df.index.min()} à {df.index.max()})")


if __name__ == "__main__":
    main()
