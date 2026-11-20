"""Build a simple OWL ontology for the medical knowledge graph (opens in Protégé)."""
import re
from pathlib import Path
import pandas as pd
from rdflib import URIRef, Graph, Namespace, Literal, RDF, RDFS, OWL, XSD, BNode
from rdflib.collection import Collection

DATA = Path(__file__).resolve().parent / "neo4j_import"
KG = Namespace("http://example.org/medical-kg#")
g = Graph(); g.bind("kg", KG); g.bind("owl", OWL)

onto = URIRef("http://example.org/medical-kg")
g.add((onto, RDF.type, OWL.Ontology))
g.add((onto, RDFS.label, Literal("Medical Knowledge Graph Ontology")))
g.add((onto, RDFS.comment, Literal("Simple ontology describing the classes and relationships of the medical KG built in Neo4j.")))

def iri(name):  # "Type 2 diabetes mellitus" -> Type_2_diabetes_mellitus
    return KG[re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")]

def cls(name, parent=None, comment=None):
    c = iri(name); g.add((c, RDF.type, OWL.Class)); g.add((c, RDFS.label, Literal(name)))
    if parent: g.add((c, RDFS.subClassOf, iri(parent)))
    if comment: g.add((c, RDFS.comment, Literal(comment)))
    return c

# ---------------- 1. Classes ----------------
cls("MedicalEntity", comment="Root class for everything in the graph")
top = {
    "Disease":    "A medical condition (MONDO ontology)",
    "Symptom":    "A sign a patient experiences (HPO ontology)",
    "Medicine":   "A drug (DrugBank)",
    "SideEffect": "An unwanted effect caused by a medicine (SIDER / HPO)",
    "LabTest":    "A laboratory test (LOINC)",
    "RiskFactor": "Something that raises the chance of a disease",
}
for c, txt in top.items(): cls(c, "MedicalEntity", txt)

# the six main classes cannot overlap
alldis = BNode(); g.add((alldis, RDF.type, OWL.AllDisjointClasses))
lst = BNode(); Collection(g, lst, [iri(c) for c in top]); g.add((alldis, OWL.members, lst))

# Disease hierarchy by body system
categories = {
    "CardiovascularDisease": ["Essential hypertension", "Coronary artery disease", "Heart failure", "Atrial fibrillation"],
    "MetabolicEndocrineDisease": ["Type 2 diabetes mellitus", "Hypothyroidism", "Obesity", "Vitamin D deficiency", "Gout", "Hyperlipidemia"],
    "RespiratoryDisease": ["Asthma", "Chronic obstructive pulmonary disease", "Acute upper respiratory infection", "Acute bronchitis", "Allergic rhinitis", "Pneumonia"],
    "InfectiousDisease": ["Influenza", "COVID-19", "Acute pharyngitis", "Gastroenteritis", "Urinary tract infection"],
    "DigestiveDisease": ["Gastro-esophageal reflux disease", "Irritable bowel syndrome", "Peptic ulcer disease", "Celiac disease", "Crohn's disease"],
    "MusculoskeletalDisease": ["Low back pain", "Osteoarthritis", "Rheumatoid arthritis", "Osteoporosis"],
    "NeurologicalDisease": ["Migraine", "Tension-type headache", "Epilepsy", "Alzheimer's disease", "Parkinson's disease"],
    "SkinDisease": ["Atopic dermatitis", "Psoriasis", "Acne vulgaris", "Contact dermatitis"],
    "KidneyUrologicalDisease": ["Chronic kidney disease", "Benign prostatic hyperplasia"],
    "ReproductiveDisease": ["Endometriosis", "Polycystic ovary syndrome"],
    "BloodDisease": ["Iron deficiency anemia"],
    "EyeDisease": ["Glaucoma"],
}
for c in categories: cls(c, "Disease")

# Risk factor hierarchy (simple, keyword based)
rf_types = {"LifestyleRiskFactor": "Diet, smoking, alcohol, activity, sleep, stress",
            "GeneticRiskFactor": "Family history and genes",
            "DemographicRiskFactor": "Age, sex, ancestry",
            "ClinicalRiskFactor": "Existing conditions and medicines",
            "EnvironmentalRiskFactor": "Pollution, exposures, infections"}
for c, t in rf_types.items(): cls(c, "RiskFactor", t)

def rf_type(name):
    n = name.lower()
    if "family history" in n or any(k in n for k in ["gene", "genotype", "hla-", "deficiency"]) and "vitamin" not in n and "iodine" not in n:
        return "GeneticRiskFactor"
    if any(k in n for k in ["age ", "female sex", "male sex", "ancestry", "pigmentation"]): return "DemographicRiskFactor"
    if any(k in n for k in ["diet", "smoking", "alcohol", "inactivity", "sedentary", "sleep", "stress",
                            "posture", "hygiene", "lifting", "hand washing", "intake", "sexual", "sun"]):
        return "LifestyleRiskFactor"
    if any(k in n for k in ["exposure", "pollution", "contaminated", "contact", "environment", "infection"]):
        return "EnvironmentalRiskFactor"
    return "ClinicalRiskFactor"

# ---------------- 2. Object properties (relationships) ----------------
def oprop(name, domain, rng, comment, inverse=None, symmetric=False):
    p = KG[name]; g.add((p, RDF.type, OWL.ObjectProperty)); g.add((p, RDFS.label, Literal(name)))
    if isinstance(domain, list):          # domain = union of several classes
        u = BNode(); lst = BNode(); Collection(g, lst, [iri(c) for c in domain])
        g.add((u, RDF.type, OWL.Class)); g.add((u, OWL.unionOf, lst)); g.add((p, RDFS.domain, u))
    else:
        g.add((p, RDFS.domain, iri(domain)))
    g.add((p, RDFS.range, iri(rng))); g.add((p, RDFS.comment, Literal(comment)))
    if symmetric: g.add((p, RDF.type, OWL.SymmetricProperty))
    if inverse:
        q = KG[inverse]; g.add((q, RDF.type, OWL.ObjectProperty)); g.add((q, RDFS.label, Literal(inverse)))
        g.add((q, OWL.inverseOf, p))

oprop("indicates", "Symptom", "Disease", "Symptom is a sign of the disease", inverse="hasSymptom")
oprop("treats", "Medicine", "Disease", "Medicine is used to treat the disease", inverse="treatedBy")
oprop("notRecommendedFor", "Medicine", "Disease", "Medicine should be avoided in the disease (contraindication)")
oprop("causes", "Medicine", "SideEffect", "Medicine can cause the side effect", inverse="causedBy")
oprop("interactsWith", "Medicine", "Medicine", "Two medicines interact when taken together", symmetric=True)
oprop("requiresTest", "Disease", "LabTest", "Lab test used to diagnose or monitor the disease", inverse="testFor")
oprop("riskFactorFor", ["RiskFactor", "Disease"], "Disease",
      "Raises the chance of developing the disease (a disease can itself be a risk factor)", inverse="hasRiskFactor")

# ---------------- 3. Data properties (attributes) ----------------
def dprop(name, domain, comment):
    p = KG[name]; g.add((p, RDF.type, OWL.DatatypeProperty)); g.add((p, RDFS.label, Literal(name)))
    g.add((p, RDFS.domain, iri(domain))); g.add((p, RDFS.range, XSD.string)); g.add((p, RDFS.comment, Literal(comment)))
dprop("hasID", "MedicalEntity", "Standard ID: MONDO, HPO, DrugBank, LOINC or RF code")
dprop("loincCode", "LabTest", "LOINC code of the test")

# ---------------- 4. Individuals (actual items from the graph) ----------------
def ind(name, klass, nid):
    i = iri(name)
    # avoid clashing with a class or another item of the same name (e.g. Obesity disease vs risk factor)
    if (i, RDF.type, OWL.Class) in g or (i, RDF.type, OWL.NamedIndividual) in g:
        i = iri(f"{name} {klass}")
    g.add((i, RDF.type, OWL.NamedIndividual)); g.add((i, RDF.type, iri(klass)))
    g.add((i, RDFS.label, Literal(name))); g.add((i, KG.hasID, Literal(nid)))
    return i

N = {k: pd.read_csv(DATA / f"nodes_{k}.csv", dtype=str) for k in top}
ids = {}  # graph id -> ontology individual

cat_of = {d: c for c, ds in categories.items() for d in ds}
for r in N["Disease"].itertuples():  ids[r.id] = ind(r.name, cat_of.get(r.name, "Disease"), r.id)
for r in N["Medicine"].itertuples(): ids[r.id] = ind(r.name, "Medicine", r.id)
for r in N["Symptom"].itertuples():  ids[r.id] = ind(r.name, "Symptom", r.id)
for r in N["LabTest"].itertuples():
    i = ind(r.name, "LabTest", r.id); ids[r.id] = i; g.add((i, KG.loincCode, Literal(r.id.split(":")[1])))
# risk factors that are really one of our diseases are merged into that disease (same as in Neo4j)
dis_by_name = {r.name.lower(): r.id for r in N["Disease"].itertuples()}
same = {"hypertension": "essential hypertension", "copd": "chronic obstructive pulmonary disease"}
for r in N["RiskFactor"].itertuples():
    match = dis_by_name.get(same.get(r.name.lower(), r.name.lower()))
    ids[r.id] = ids[match] if match else ind(r.name, rf_type(r.name), r.id)

# ---------------- 5. Facts: all curated layers (side effects left out for size) ----------------
def facts(rel, prop):
    e = pd.read_csv(DATA / f"edges_{rel}.csv", dtype=str)
    for r in e.itertuples(): g.add((ids[r.source_id], KG[prop], ids[r.target_id]))
    return len(e)
counts = {p: facts(r, p) for r, p in [("RISK_FACTOR_FOR", "riskFactorFor"),
                                     ("REQUIRES_TEST", "requiresTest"),
                                     ("INTERACTS_WITH", "interactsWith"),
                                     ("INDICATES", "indicates"),
                                     ("TREATS", "treats"),
                                     ("NOT_RECOMMENDED_FOR", "notRecommendedFor")]}

out = Path(__file__).resolve().parent / "medical_kg_ontology.owl"
g.serialize(out, format="xml")
print("triples:", len(g), "| facts:", counts, "| saved", out)
