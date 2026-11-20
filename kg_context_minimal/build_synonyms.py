"""
Step 0 – build the keyword list (synonyms.csv) for every node in the graph.

Each row = one way of writing a node:  node_id, label, name, term
Sources:
  1. the node's own name (every node)
  2. HPO exact synonyms for symptoms / side effects (needs hp.obo, optional)
  3. everyday words and brand names written by hand (LAY below)

Run:  python build_synonyms.py [path/to/hp.obo]
"""
import re, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
IMP = HERE.parent / "neo4j_import"
LABELS = ["Disease", "Symptom", "Medicine", "SideEffect", "LabTest", "RiskFactor"]

# everyday words -> node NAME (as in the node files). One term may point to two nodes.
LAY = {
    "Disease": {
        "Essential hypertension": ["hypertension", "high blood pressure", "high bp", "bp"],
        "Hyperlipidemia": ["high cholesterol", "cholesterol", "hypercholesterolemia"],
        "Coronary artery disease": ["heart disease", "coronary heart disease", "cad", "ischemic heart disease"],
        "Heart failure": ["chf", "congestive heart failure", "cardiac failure"],
        "Atrial fibrillation": ["afib", "a fib", "irregular heartbeat"],
        "Type 2 diabetes mellitus": ["diabetes", "type 2 diabetes", "t2dm", "t2d", "sugar", "high blood sugar", "diabetes mellitus"],
        "Hypothyroidism": ["underactive thyroid", "low thyroid"],
        "Obesity": ["overweight", "obese"],
        "Vitamin D deficiency": ["low vitamin d", "vit d deficiency"],
        "Chronic obstructive pulmonary disease": ["copd", "emphysema", "chronic bronchitis"],
        "Acute upper respiratory infection": ["common cold", "a cold", "upper respiratory infection", "uri"],
        "Acute bronchitis": ["bronchitis", "chest cold"],
        "Allergic rhinitis": ["hay fever", "nasal allergy", "allergies"],
        "Pneumonia": ["lung infection"],
        "Influenza": ["flu"],
        "COVID-19": ["covid", "covid 19", "coronavirus", "sars cov 2"],
        "Acute pharyngitis": ["strep throat", "pharyngitis", "throat infection"],
        "Gastroenteritis": ["stomach flu", "stomach bug", "tummy bug"],
        "Urinary tract infection": ["uti", "bladder infection", "urine infection"],
        "Gastro-esophageal reflux disease": ["gerd", "acid reflux", "reflux"],
        "Irritable bowel syndrome": ["ibs"],
        "Peptic ulcer disease": ["stomach ulcer", "peptic ulcer", "ulcer"],
        "Celiac disease": ["coeliac disease", "coeliac", "celiac"],
        "Crohn's disease": ["crohns", "crohn disease"],
        "Low back pain": ["lower back pain"],
        "Osteoarthritis": ["wear and tear arthritis"],
        "Rheumatoid arthritis": ["rheumatoid"],
        "Osteoporosis": ["brittle bones"],
        "Migraine": ["migraines"],
        "Tension-type headache": ["tension headache"],
        "Epilepsy": ["epileptic", "seizure disorder"],
        "Alzheimer's disease": ["alzheimers", "alzheimer"],
        "Parkinson's disease": ["parkinsons", "parkinson"],
        "Atopic dermatitis": ["atopic eczema"],
        "Acne vulgaris": ["acne", "pimples"],
        "Chronic kidney disease": ["ckd", "kidney disease", "chronic renal failure"],
        "Benign prostatic hyperplasia": ["bph", "enlarged prostate"],
        "Polycystic ovary syndrome": ["pcos", "polycystic ovaries"],
        "Iron deficiency anemia": ["anemia", "anaemia", "iron deficiency", "low iron"],
    },
    "Medicine": {
        "Acetaminophen": ["paracetamol", "tylenol", "crocin", "panadol", "calpol"],
        "Ibuprofen": ["advil", "motrin", "brufen", "nurofen"],
        "Albuterol": ["salbutamol", "ventolin"],
        "Aspirin": ["acetylsalicylic acid"],
        "Omeprazole": ["prilosec"],
        "Atorvastatin": ["lipitor"],
        "Simvastatin": ["zocor"],
        "Metformin": ["glucophage"],
        "Sertraline": ["zoloft"],
        "Levothyroxine": ["synthroid", "thyroxine", "eltroxin"],
        "Amoxicillin": ["amoxil"],
        "Lisinopril": ["zestril", "prinivil"],
        "Amlodipine": ["norvasc"],
        "Warfarin": ["coumadin"],
        "Apixaban": ["eliquis"],
        "Clopidogrel": ["plavix"],
        "Sumatriptan": ["imitrex"],
        "Semaglutide": ["ozempic", "wegovy"],
        "Insulin glargine": ["lantus", "insulin"],
        "Montelukast": ["singulair"],
        "Fluticasone propionate": ["fluticasone", "flonase", "flovent"],
        "Budesonide": ["pulmicort"],
        "Cetirizine": ["zyrtec"],
        "Loratadine": ["claritin"],
        "Oseltamivir": ["tamiflu"],
        "Nirmatrelvir": ["paxlovid"],
        "Pantoprazole": ["protonix", "pantop"],
        "Famotidine": ["pepcid"],
        "Naproxen": ["aleve", "naprosyn"],
        "Hydrochlorothiazide": ["hctz"],
        "Empagliflozin": ["jardiance"],
        "Dapagliflozin": ["farxiga", "forxiga"],
        "Sitagliptin": ["januvia"],
        "Levodopa": ["l dopa"],
        "Donepezil": ["aricept"],
        "Isotretinoin": ["accutane"],
        "Tamsulosin": ["flomax"],
        "Finasteride": ["proscar"],
        "Latanoprost": ["xalatan"],
        "Valproic acid": ["valproate", "depakote"],
        "Phenoxymethylpenicillin": ["penicillin v", "penicillin"],
        "Alendronic acid": ["alendronate", "fosamax"],
        "Risedronic acid": ["risedronate"],
        "Zoledronic acid": ["zoledronate"],
        "Ferrous sulfate": ["iron tablets", "iron supplement", "ferrous sulphate"],
        "Cholecalciferol": ["vitamin d3"],
        "Ergocalciferol": ["vitamin d2"],
        "Medroxyprogesterone acetate": ["medroxyprogesterone"],
        "Norethisterone": ["norethindrone"],
        "Ethinylestradiol": ["ethinyl estradiol"],
        "Sulfamethoxazole": ["bactrim", "co trimoxazole"],
        "Trimethoprim": ["bactrim", "co trimoxazole"],
        "Carbidopa": ["sinemet"],
    },
    "Symptom": {
        "Shortness of breath": ["breathless", "breathlessness", "cant breathe", "cannot breathe", "out of breath",
                                "difficulty breathing", "short of breath", "breathing difficulty"],
        "Fever": ["high temperature", "temperature", "feverish"],
        "Fatigue": ["tired", "tiredness", "exhausted", "exhaustion", "no energy"],
        "Headache": ["head ache", "head pain", "headaches"],
        "Cough": ["coughing"],
        "Sore throat": ["throat pain", "painful throat"],
        "Runny nose": ["running nose"],
        "Nasal congestion": ["blocked nose", "stuffy nose"],
        "Nausea": ["nauseous", "feel sick", "feeling sick"],
        "Vomiting": ["throwing up", "vomit", "being sick"],
        "Diarrhea": ["diarrhoea", "loose stools", "loose motions"],
        "Abdominal pain": ["stomach ache", "stomach pain", "tummy pain", "belly pain", "tummy ache"],
        "Joint pain": ["aching joints", "painful joints", "joint ache"],
        "Itching": ["itchy", "itch"],
        "Frequent urination": ["peeing a lot", "urinating often", "frequent peeing"],
        "Painful urination": ["burning urine", "burning when peeing", "pain when peeing"],
        "Excessive thirst": ["very thirsty", "always thirsty"],
        "Weight gain": ["gaining weight", "put on weight"],
        "Weight loss": ["losing weight", "lost weight"],
        "Dizziness": ["dizzy", "lightheaded", "light headed"],
        "Palpitations": ["racing heart", "heart pounding", "heart racing"],
        "Wheezing": ["wheezy", "wheeze"],
        "Loss of smell": ["cant smell", "lost my smell"],
        "Bloating": ["bloated"],
        "Skin rash": ["rash"],
        "Peripheral edema": ["swollen legs", "swollen ankles", "swollen feet", "leg swelling"],
        "Blurred vision": ["blurry vision"],
        "Memory impairment": ["memory loss", "forgetfulness", "forgetful"],
        "Resting tremor": ["shaking", "tremor", "shaky hands"],
        "Chest tightness": ["tight chest"],
    },
}


def norm(s: str) -> str:
    """lowercase, drop apostrophes, everything else non-alphanumeric -> one space"""
    s = s.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def hpo_exact_synonyms(path):
    syn, cur = {}, None
    for line in open(path, encoding="utf-8"):
        if line.startswith("id: "): cur = line[4:].strip()
        elif line.startswith("name: ") and cur:          # official HPO name, e.g. "Dyspnea"
            syn.setdefault(cur, []).append(line[6:].strip())
        elif line.startswith("synonym: ") and " EXACT" in line and cur:
            m = re.match(r'synonym: "(.*?)"', line)
            if m: syn.setdefault(cur, []).append(m.group(1))
    return syn


def main():
    hpo = hpo_exact_synonyms(sys.argv[1]) if len(sys.argv) > 1 else {}
    rows, missing = [], []
    for lab in LABELS:
        nodes = pd.read_csv(IMP / f"nodes_{lab}.csv", dtype=str)
        by_name = {n.lower(): i for i, n in zip(nodes.id, nodes.name)}
        for i, n in zip(nodes.id, nodes.name):
            rows.append((i, lab, n, norm(n)))                     # 1. own name
            for s in hpo.get(i, []) if lab in ("Symptom", "SideEffect") else []:
                rows.append((i, lab, n, norm(s)))                 # 2. HPO synonyms
        for name, terms in LAY.get(lab, {}).items():              # 3. everyday words
            nid = by_name.get(name.lower())
            if not nid: missing.append((lab, name)); continue
            rows.extend((nid, lab, name, norm(t)) for t in terms)
    df = pd.DataFrame(rows, columns=["node_id", "label", "name", "term"]).drop_duplicates()
    df = df[df.term.str.len() >= 2]
    df.to_csv(HERE / "synonyms.csv", index=False)
    print(f"synonyms.csv: {len(df)} terms for {df.node_id.nunique()} nodes")
    if missing: print("names in LAY not found in the graph:", missing)


if __name__ == "__main__":
    main()
