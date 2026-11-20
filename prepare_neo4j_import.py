"""
Prepare the medical KG CSVs for Neo4j.

Input  (same folder or pass a path):  complete_node_list.csv, complete_kg_dataset.csv
Output (./neo4j_import/):             one node file per label, one edge file per relationship

Fixes applied:
  1. Bare numeric IDs are made globally unique:
       SideEffect "2027"  -> "HP:0002027"   (they are HPO term numbers from SIDER)
  2. The 32 MedlinePlus rows have source/target swapped (e.g. "pneumonia --INDICATES--> fever"
     with pneumonia typed as Symptom). They are flipped so Symptom -> Disease, and names are
     matched to the existing canonical HP/MONDO nodes where possible. Unmatched ones get an
     "MP:" id and confidence='low'. Self-loops are dropped.
  3. TREATED_BY (Medicine -> Disease) is renamed TREATS, so the arrow reads correctly.
  4. The JSON 'metadata' column is expanded into real edge properties
     (loinc_code, purpose, evidence_level, severity, description).
  5. INTERACTS_WITH is symmetric: A-B and B-A duplicates are collapsed to one row.
"""
import json, sys
from pathlib import Path
import pandas as pd

# ===================== SETTINGS (edit these) =====================
DROP_MEDLINEPLUS      = True   # True = delete the 32 MedlinePlus rows instead of flipping them
REMOVE_CONTRADICTIONS = True   # True = delete drug-disease pairs that are both TREATS and NOT_RECOMMENDED_FOR
# ================================================================

src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
out = Path("neo4j_import"); out.mkdir(exist_ok=True)

nodes = pd.read_csv(src / "complete_node_list.csv", dtype=str)
edges = pd.read_csv(src / "complete_kg_dataset.csv", dtype=str)

# ---------- canonical name lookup (prefixed IDs only) ----------
canon = nodes[nodes.node_id.str.contains(":")]
lookup = {(r.node_type, r.node_name.strip().lower()): r.node_id for r in canon.itertuples()}

def hp(i):  return f"HP:{int(i):07d}"

# ---------- 1. fix SIDER side-effect IDs ----------
se_mask_e = edges.target_type.eq("SideEffect")
edges.loc[se_mask_e, "target_id"] = edges.loc[se_mask_e, "target_id"].map(hp)

# ---------- 2. flip + remap MedlinePlus rows ----------
mp = edges.data_source.eq("MedlinePlus")
if DROP_MEDLINEPLUS:
    edges = edges[~mp]
    mp = edges.data_source.eq("MedlinePlus")   # now all False, so the loop below does nothing
new_nodes = []
def resolve(name, ntype):
    key = (ntype, name.strip().lower())
    if key in lookup: return lookup[key], False
    nid = f"MP:{ntype[:3].upper()}:{name.strip().lower().replace(' ', '_')}"
    new_nodes.append((nid, ntype, name.strip().capitalize()))
    return nid, True

fixed = []
for r in edges[mp].itertuples():
    dis_name, sym_name = r.source_name, r.target_name   # swapped in source data
    if dis_name.lower() == sym_name.lower():
        continue
    d_id, d_new = resolve(dis_name, "Disease")
    s_id, s_new = resolve(sym_name, "Symptom")
    fixed.append(dict(source_id=s_id, source_type="Symptom", source_name=sym_name,
                      relation="INDICATES", target_id=d_id, target_type="Disease",
                      target_name=dis_name, data_source="MedlinePlus",
                      metadata=json.dumps({"confidence": "low"})))
edges = pd.concat([edges[~mp], pd.DataFrame(fixed)], ignore_index=True)

# ---------- 3. rename TREATED_BY ----------
edges["relation"] = edges.relation.replace({"TREATED_BY": "TREATS"})

if REMOVE_CONTRADICTIONS:
    key = edges.source_id + "|" + edges.target_id
    both = set(key[edges.relation.eq("TREATS")]) & set(key[edges.relation.eq("NOT_RECOMMENDED_FOR")])
    edges = edges[~(key.isin(both) & edges.relation.isin(["TREATS", "NOT_RECOMMENDED_FOR"]))]
    print(f"Removed {len(both)} contradictory drug-disease pairs")

# ---------- 4. expand metadata ----------
meta = edges.metadata.fillna("{}").map(json.loads).apply(pd.Series)
edges = pd.concat([edges.drop(columns="metadata"), meta], axis=1)

# ---------- 4b. drop the two celiac lab rows with wrong LOINC codes ----------
#   "Total IgA" was coded as Total IgE (19113-0); "Endomysial Antibody IgA" reused tTG's code (31017-7)
celiac_lab = edges.relation.eq("REQUIRES_TEST") & edges.source_id.eq("MONDO:0005130")
wrong = celiac_lab & (edges.target_id.eq("LOINC:19113-0") |
                      (edges.target_id.eq("LOINC:31017-7") & edges.purpose.eq("Confirmatory test")))
edges = edges[~wrong]
print(f"Removed {wrong.sum()} celiac lab rows with wrong LOINC codes")

# ---------- 5. dedupe symmetric interactions ----------
ddi = edges.relation.eq("INTERACTS_WITH")
pair = edges.loc[ddi].apply(lambda r: tuple(sorted([r.source_id, r.target_id])), axis=1)
edges = pd.concat([edges[~ddi], edges[ddi][~pair.duplicated()]], ignore_index=True)

# ---------- build final node table from the edges actually used ----------
ends = pd.concat([
    edges[["source_id", "source_type", "source_name"]].set_axis(["id", "label", "name"], axis=1),
    edges[["target_id", "target_type", "target_name"]].set_axis(["id", "label", "name"], axis=1),
])
# prefer canonical capitalised names from the node list
name_by_id = dict(zip(nodes.node_id, nodes.node_name))
name_by_id.update({n: nm for n, _, nm in new_nodes})
ends["name"] = ends.id.map(name_by_id).fillna(ends.name)
final_nodes = ends.drop_duplicates(["id", "label"])   # same ID may be both a Symptom and a SideEffect

for label, g in final_nodes.groupby("label"):
    g[["id", "name"]].to_csv(out / f"nodes_{label}.csv", index=False)

keep = ["source_id", "target_id", "data_source", "loinc_code", "purpose",
        "evidence_level", "severity", "description", "confidence"]
for rel, g in edges.groupby("relation"):
    cols = [c for c in keep if c in g and g[c].notna().any()]
    g[cols].to_csv(out / f"edges_{rel}.csv", index=False)

print("Nodes:", final_nodes.label.value_counts().to_dict(), "total", len(final_nodes))
print("Edges:", edges.relation.value_counts().to_dict(), "total", len(edges))
print("Wrote files to", out.resolve())
