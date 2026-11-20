"""
Final small fixes (run after build_corrected_layers.py):
  1. Remove a drug-drug "interaction" whose own description says there is no interaction.
  2. Merge risk factors that mean the same thing.
Safe to run more than once.
"""
from pathlib import Path
import pandas as pd

IMP = Path(__file__).resolve().parent / "neo4j_import"

# ---- 1. non-interaction: Atorvastatin + Amoxicillin ("No significant pharmacokinetic interaction expected")
ddi = pd.read_csv(IMP / "edges_INTERACTS_WITH.csv", dtype=str)
fake = ddi.description.str.contains("No significant", case=False, na=False)
ddi[~fake].to_csv(IMP / "edges_INTERACTS_WITH.csv", index=False)
print(f"Removed {fake.sum()} non-interaction(s)")

# ---- 2. merge same-meaning risk factors: old id -> kept id
MERGE = {
    "RF:SEDENTARY_LIFESTYLE": "RF:PHYSICAL_INACTIVITY",          # same concept
    "RF:NSAID_OVERUSE": "RF:NSAID_USE",                          # overuse is a form of use
    "RF:ATOPIC_DERMATITIS_HISTORY": "RF:ATOPIC_DERMATITIS",      # same condition (then merged into the disease in Neo4j)
}
rf = pd.read_csv(IMP / "nodes_RiskFactor.csv", dtype=str)
e = pd.read_csv(IMP / "edges_RISK_FACTOR_FOR.csv", dtype=str)
e["source_id"] = e.source_id.replace(MERGE)
dups = e.duplicated(["source_id", "target_id"])
e[~dups].to_csv(IMP / "edges_RISK_FACTOR_FOR.csv", index=False)
gone = rf.id.isin(MERGE)
rf[~gone].to_csv(IMP / "nodes_RiskFactor.csv", index=False)
print(f"Merged {gone.sum()} risk factor(s); duplicate links dropped: {dups.sum()}")
