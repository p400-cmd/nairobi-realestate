import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

RAW_PATH = Path("data/raw/listings_raw.csv")
CLEAN_PATH = Path("data/processed/listings_clean.csv")


def parse_price(price_str: str) -> float | None:
    if pd.isna(price_str):
        return None
    digits = re.sub(r"[^\d]", "", str(price_str))
    return float(digits) if digits else None


def parse_count(val: str) -> int | None:
    if pd.isna(val):
        return None
    match = re.search(r"\d+", str(val))
    return int(match.group()) if match else None


LOCATION_MAP = {
    "westlands area": "Westlands",
    "kilimani area": "Kilimani",
    "kileleshwa area": "Kileleshwa",
    "lavington area": "Lavington",
    "karen area": "Karen",
    "ruaka area": "Ruaka",
    "kasarani area": "Kasarani",
    "parklands area": "Parklands",
    "parklands": "Parklands",
    "riverside": "Westlands",
    "rhapta road": "Westlands",
    "ngong": "Other",
    "garden estate": "Other",
}


def standardize_location(loc: str) -> str:
    if pd.isna(loc):
        return "Unknown"
    primary = loc.split(",")[0].strip()
    cleaned = primary.lower()
    return LOCATION_MAP.get(cleaned, primary.title())


def remove_outliers(df: pd.DataFrame, col: str) -> pd.DataFrame:
    lo, hi = df[col].quantile([0.01, 0.99])
    before = len(df)
    df = df[(df[col] >= lo) & (df[col] <= hi)]
    log.info(
        f"Outlier removal on {col}: dropped {before - len(df)} rows "
        f"(1st/99th pct: {lo:,.0f} / {hi:,.0f})"
    )
    return df


def clean(raw_path: Path = RAW_PATH, clean_path: Path = CLEAN_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path)
    log.info(f"Loaded: {len(df)} rows")

    # Parse
    df["price"] = df["price"].apply(parse_price)
    df["bedrooms"] = df["bedrooms"].apply(parse_count)
    df["bathrooms"] = df["bathrooms"].apply(parse_count)
    df["location"] = df["location"].apply(standardize_location)

    # Drop missing price — target variable, no imputation
    before = len(df)
    df = df.dropna(subset=["price"])
    log.info(f"Dropped {before - len(df)} rows with missing price")

    # Drop exact duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["listing_url"])
    log.info(f"Dropped {before - len(df)} duplicate listings")

    OUT_OF_SCOPE = ["Nyali", "Nyali Area", "Mtwapa", "Diani", "Kizingo", "Syokimau"]
    df = df[~df["location"].isin(OUT_OF_SCOPE)]

    # replacing bedrooms/bathrooms with median per location
    for col in ["bedrooms", "bathrooms"]:
        df[col] = df.groupby("location")[col].transform(lambda x: x.fillna(x.median()))
        df[col] = df[col].fillna(df[col].median())
        df[col] = df[col].astype(int)

    # Outlier removal on price
    df = remove_outliers(df, "price")

    # Log-transform price
    df["log_price"] = np.log(df["price"])

    df = df.reset_index(drop=True)

    log.info(f"Final clean dataset: {len(df)} rows")
    log.info(f"Missing values:\n{df.isnull().sum()}")

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(clean_path, index=False)
    log.info(f"Saved → {clean_path}")

    return df


if __name__ == "__main__":
    clean()
