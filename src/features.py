import pandas as pd
import numpy as np
from pathlib import Path

CLEAN_PATH = Path("data/processed/listings_clean.csv")
FEATURES_PATH = Path("data/processed/listings_features.csv")

TIER_MAP = {
    "Westlands": "Premium",
    "Muthaiga": "Premium",
    "Parklands": "Premium",
    "General Mathenge": "Premium",
    "Brookside": "Premium",
    "Kiambu Road": "Premium",
    "Gigiri": "Premium",

    "Lavington": "Mid",
    "Kileleshwa": "Mid",
    "Kilimani": "Mid",
    "South B": "Mid",
    "Kitisuru": "Mid",
    "Other": "Mid",
    "Karen": "Mid",
    "Lower Kabete": "Mid",
    "Loresho": "Mid",
    "Valley Arcade": "Mid",
    "Spring Valley": "Mid",
    "Mombasa Road": "Mid",
    "Eastleigh": "Mid",
    "Embakasi": "Mid",
    "Ngong Road": "Mid",
    "Langata": "Mid",
}


def engineer_features(clean_path=CLEAN_PATH, out_path=FEATURES_PATH):
    df = pd.read_csv(clean_path)

    # --- Size signal ---
    df["bed_bath_ratio"] = df["bedrooms"] / df["bathrooms"].replace(0, 1)
    df = df.drop(columns=["bathrooms"])

    # --- Neighborhood tier ---
    df["tier"] = df["location"].map(TIER_MAP)

    unmapped = sorted(df.loc[df["tier"].isna(), "location"].unique())
    if unmapped:
        print(f"\n⚠ WARNING: {len(unmapped)} location(s) not in TIER_MAP, "
              f"defaulted to 'Mid': {unmapped}")
        print("  Review these: (1) confirm each is actually within Nairobi "
              "(see the Syokimau lesson), (2) add an explicit, justified "
              "tier assignment to TIER_MAP instead of relying on this default.\n")
    df["tier"] = df["tier"].fillna("Mid")

    tier_dummies = pd.get_dummies(df["tier"], prefix="tier", drop_first=True)
    assert "tier_Affordable" not in tier_dummies.columns, "Reference category not dropped as expected"
    df = pd.concat([df, tier_dummies.astype(int)], axis=1)

    df.to_csv(out_path, index=False)
    print(f"Features saved: {out_path}")
    print(df[["location", "tier"] + list(tier_dummies.columns) + ["bedrooms", "bed_bath_ratio"]].head(10))
    print("\nTier counts (flag n<10 as unreliable for coefficient interpretation):")
    print(df["tier"].value_counts())
    print("\nLocation counts within tiers:")
    print(df.groupby("tier")["location"].value_counts())


if __name__ == "__main__":
    engineer_features()
