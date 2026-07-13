import pandas as pd
import numpy as np
from pathlib import Path

CLEAN_PATH = Path("data/processed/listings_clean.csv")
FEATURES_PATH = Path("data/processed/listings_features.csv")

TIER_MAP = {
    "Westlands": "Premium",
    "Lavington": "Mid",
    "Kileleshwa": "Mid",
    "Kilimani": "Mid",
    "Syokimau": "Mid",
    "Parklands": "Mid",
    "South B": "Mid",
    "Kitisuru": "Mid",
    "Other": "Mid",
}


def engineer_features(clean_path=CLEAN_PATH, out_path=FEATURES_PATH):
    df = pd.read_csv(clean_path)

    df["bed_bath_ratio"] = df["bedrooms"] / df["bathrooms"].replace(0, 1)
    df = df.drop(columns=["bathrooms"])

    # --- Neighborhood tier ---
    df["tier"] = df["location"].map(TIER_MAP)

    tier_dummies = pd.get_dummies(df["tier"], prefix="tier", drop_first=True)
    assert "tier_Affordable" not in tier_dummies.columns, "Reference category not dropped as expected"
    df = pd.concat([df, tier_dummies.astype(int)], axis=1)

    df.to_csv(out_path, index=False)
    print(f"Features saved: {out_path}")
    print(df[["location", "tier"] + list(tier_dummies.columns) + ["bedrooms", "bed_bath_ratio"]].head(10))
    print("\nTier counts (flag n<10 as unreliable for coefficient interpretation):")
    print(df["tier"].value_counts())
    print("\nLocation counts within tiers (Kitisuru n=1, South B n=2, Parklands n=4 -- "
          "all folded into Mid; individually unreliable but no longer distort a "
          "standalone category coefficient):")
    print(df.groupby("tier")["location"].value_counts())


if __name__ == "__main__":
    engineer_features()
