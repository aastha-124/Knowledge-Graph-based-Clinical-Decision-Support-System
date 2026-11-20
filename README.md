# Medical Knowledge Graph – Neo4j build (corrected version)

## Contents
- `neo4j_import/` – the 13 final CSVs to load into Neo4j (ready to use)
- `load_kg.cypher` – loads the CSVs into Neo4j
- `review_checklist.csv` – every new symptom / treatment / contraindication link, with its source and lookup links, for manual checking
- `medical_kg_ontology.owl` – ontology for Protégé, matching the graph
- `old_layers_backup/` – the original (incorrect) symptom, treatment and contraindication files, kept for comparison
- Scripts:
  - `prepare_neo4j_import.py` – cleans the raw data (`complete_*.csv`)
  - `build_corrected_layers.py` + `curated.py` + `hpo.py` – replace the symptom, treatment and contraindication layers with curated data
  - `final_fixes.py` – removes one non-interaction and merges 3 same-meaning risk factors
  - `build_ontology.py` – regenerates the ontology
  - Run order: prepare_neo4j_import.py → build_corrected_layers.py (needs hp.obo) → final_fixes.py → build_ontology.py

## What changed in this version
1. **Treatments rebuilt**: 153 links from clinical guidelines (ADA, GINA, ACR, NICE, AHA/ACC …). All DrugBank IDs verified. 62 links also confirmed by PharmacotherapyDB (physician-curated); none contradicted.
2. **Symptoms rebuilt**: 190 links based on MedlinePlus; every symptom mapped to its official HPO ID (HPO release 2026-09-01).
3. **Contraindications rebuilt**: 14 well-established label-level warnings, each with a reason.
4. **Bug fix**: side effects that share an ID with a symptom (e.g. Nausea) were dropped before; all 311 side effects and 967 side-effect links now load.
5. Duplicate risk factors (e.g. "Asthma", "Obesity") are merged into their diseases when loading.
6. Removed Atorvastatin–Amoxicillin from interactions (its description said there is no interaction).
7. Merged same-meaning risk factors: Sedentary lifestyle → Physical inactivity; NSAID overuse → NSAID use; Atopic dermatitis history → Atopic dermatitis. Similar-looking pairs with different meanings (e.g. Smoking vs Smoking or secondhand smoke exposure) are kept separate on purpose.

## Expected result in Neo4j
- Nodes: SideEffect 311, Medicine 118, RiskFactor 110, Symptom 102, LabTest 67, Disease 45 = **753**
- Relationships: CAUSES 967, RISK_FACTOR_FOR 226, REQUIRES_TEST 195, INDICATES 190, TREATS 153, INTERACTS_WITH 44, NOT_RECOMMENDED_FOR 14 = **1,789**

## Known limitations
- Essential hypertension and Hyperlipidemia have no symptoms (they usually cause none). Celiac disease has no drug treatment (the treatment is a gluten-free diet).
- The 96 newly added medicines have no side-effect or interaction links yet.
- Treatment and symptom lists are a curated draft. Check them with `review_checklist.csv`.
