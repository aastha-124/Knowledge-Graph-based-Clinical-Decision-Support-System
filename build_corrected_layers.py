"""
Replace the three unreliable layers with curated data.

Reads : medical_kg/neo4j_import/  (current cleaned files)
        curated.py                (symptoms, treatments, contraindications)
        hp.obo                    (to look up official HPO IDs)
Writes: medical_kg/neo4j_import/  nodes_Symptom, nodes_Medicine,
                                  edges_INDICATES, edges_TREATS, edges_NOT_RECOMMENDED_FOR
        medical_kg/review_checklist.csv   (one row per new link, with lookup links)
Old versions are copied to medical_kg/old_layers_backup/.
"""
import shutil, sys
from pathlib import Path
import pandas as pd
from hpo import load
from curated import SYMPTOMS, DISPLAY, TREATMENTS, CONTRAINDICATIONS

KG = Path(__file__).resolve().parent
IMP = KG / "neo4j_import"
HPO_FILE = sys.argv[1] if len(sys.argv) > 1 else "hp.obo"
PHARMDB = sys.argv[2] if len(sys.argv) > 2 else None

# ---- backup the files we are replacing
bk = KG / "old_layers_backup"; bk.mkdir(exist_ok=True)
for f in ["nodes_Symptom", "nodes_Medicine", "edges_INDICATES", "edges_TREATS", "edges_NOT_RECOMMENDED_FOR"]:
    if not (bk / f"{f}.csv").exists():
        shutil.copy(IMP / f"{f}.csv", bk / f"{f}.csv")

dis = pd.read_csv(IMP / "nodes_Disease.csv")
dis_id = dict(zip(dis.name, dis.id))
assert set(SYMPTOMS) == set(dis.name) == set(TREATMENTS), "curated diseases must match the 45 graph diseases"

old_sym = pd.read_csv(bk / "nodes_Symptom.csv"); old_sym_name = dict(zip(old_sym.id, old_sym.name))
old_med = pd.read_csv(bk / "nodes_Medicine.csv")

_, EXACT, RELATED = load(HPO_FILE)
review = []

# ---------------- symptoms ----------------
sym_nodes, ind_edges = {}, []
for d, syms in SYMPTOMS.items():
    for s in syms:
        hit = EXACT.get(s) or RELATED.get(s)
        if not hit: raise SystemExit(f"No HPO term for '{s}' ({d})")
        hid, official = hit
        name = old_sym_name.get(hid) or DISPLAY.get(s) or official
        sym_nodes[hid] = name
        ind_edges.append(dict(source_id=hid, target_id=dis_id[d], data_source="MedlinePlus", hpo_name=official))
        review.append(dict(layer="Symptom", disease=d, item=sym_nodes[hid], item_id=hid, hpo_official_name=official,
                           source="MedlinePlus",
                           check_link=f"https://medlineplus.gov/search/?query={d.replace(' ', '+')}+symptoms",
                           id_link=f"https://hpo.jax.org/browse/term/{hid}"))

# ---------------- treatments ----------------
pharm = {}
if PHARMDB:
    p = pd.read_csv(PHARMDB, sep="\t")
    alias = {"Essential hypertension": "hypertension", "Chronic kidney disease": "chronic kidney failure",
             "Epilepsy": "epilepsy syndrome", "Iron deficiency anemia": "anemia"}
    for d in TREATMENTS:
        sub = p[p.disease.str.lower() == alias.get(d, d).lower()]
        if len(sub): pharm[d] = dict(zip(sub.drugbank_id, sub.category))

med_nodes = dict(zip(old_med.id, old_med.name))
treat_edges = []
for d, (src, drugs) in TREATMENTS.items():
    for did, dname in drugs:
        med_nodes.setdefault(did, dname)
        treat_edges.append(dict(source_id=did, target_id=dis_id[d], data_source=src))
        conf = "n/a (disease not covered)" if d not in pharm else \
               ("yes" if pharm[d].get(did) in ("DM", "SYM") else "not listed")
        review.append(dict(layer="Treatment", disease=d, item=med_nodes[did], item_id=did, source=src,
                           pharmacotherapydb_confirmed=conf,
                           check_link=f"https://go.drugbank.com/drugs/{did}",
                           id_link=f"https://go.drugbank.com/drugs/{did}"))

# ---------------- contraindications ----------------
nr_edges = []
for did, dname, d, reason, src in CONTRAINDICATIONS:
    med_nodes.setdefault(did, dname)
    nr_edges.append(dict(source_id=did, target_id=dis_id[d], data_source=src, reason=reason))
    review.append(dict(layer="Contraindication", disease=d, item=med_nodes[did], item_id=did, source=src,
                       reason=reason, check_link=f"https://go.drugbank.com/drugs/{did}",
                       id_link=f"https://go.drugbank.com/drugs/{did}"))

# ---------------- checks ----------------
T = pd.DataFrame(treat_edges); N = pd.DataFrame(nr_edges); I = pd.DataFrame(ind_edges)
both = T.merge(N, on=["source_id", "target_id"])
assert both.empty, f"contradiction: {both}"
for df, name in [(T, "TREATS"), (N, "NOT_RECOMMENDED_FOR"), (I, "INDICATES")]:
    assert not df.duplicated(["source_id", "target_id"]).any(), f"duplicate {name}"

# ---------------- write ----------------
pd.DataFrame(sorted(sym_nodes.items()), columns=["id", "name"]).to_csv(IMP / "nodes_Symptom.csv", index=False)
pd.DataFrame(sorted(med_nodes.items()), columns=["id", "name"]).to_csv(IMP / "nodes_Medicine.csv", index=False)
I.to_csv(IMP / "edges_INDICATES.csv", index=False)
T.to_csv(IMP / "edges_TREATS.csv", index=False)
N.to_csv(IMP / "edges_NOT_RECOMMENDED_FOR.csv", index=False)

rv = pd.DataFrame(review)
rv["your_check"] = ""           # fill in: correct / wrong / unsure
rv["notes"] = ""
cols = ["layer", "disease", "item", "item_id", "source", "hpo_official_name", "reason",
        "pharmacotherapydb_confirmed", "check_link", "id_link", "your_check", "notes"]
rv[[c for c in cols if c in rv]].to_csv(KG / "review_checklist.csv", index=False)

print(f"Symptoms: {len(sym_nodes)} nodes, {len(I)} INDICATES links")
print(f"Medicines: {len(med_nodes)} nodes ({len(med_nodes) - len(old_med)} new), {len(T)} TREATS links")
print(f"Contraindications: {len(N)} NOT_RECOMMENDED_FOR links")
print(f"Review checklist: {len(rv)} rows -> {KG / 'review_checklist.csv'}")
