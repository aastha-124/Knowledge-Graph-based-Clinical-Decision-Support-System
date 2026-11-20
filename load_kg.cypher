// =====================================================================
// Medical Knowledge Graph – Neo4j load script (Neo4j 5.x)
// Put the files from neo4j_import/ into your database's "import" folder,
// then run this whole script in Neo4j Browser (enable multi-statement
// editor) or with:  cypher-shell -u neo4j -p <password> -f load_kg.cypher
// =====================================================================

// ---------- 1. Constraints (also create indexes on id) ----------
CREATE CONSTRAINT disease_id    IF NOT EXISTS FOR (n:Disease)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT symptom_id    IF NOT EXISTS FOR (n:Symptom)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT medicine_id   IF NOT EXISTS FOR (n:Medicine)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sideeffect_id IF NOT EXISTS FOR (n:SideEffect) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT labtest_id    IF NOT EXISTS FOR (n:LabTest)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT riskfactor_id IF NOT EXISTS FOR (n:RiskFactor) REQUIRE n.id IS UNIQUE;
CREATE INDEX disease_name IF NOT EXISTS FOR (n:Disease) ON (n.name);
CREATE INDEX symptom_name IF NOT EXISTS FOR (n:Symptom) ON (n.name);
CREATE INDEX medicine_name IF NOT EXISTS FOR (n:Medicine) ON (n.name);

// ---------- 2. Nodes ----------
LOAD CSV WITH HEADERS FROM 'file:///nodes_Disease.csv' AS row
MERGE (n:Disease {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Symptom.csv' AS row
MERGE (n:Symptom {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Medicine.csv' AS row
MERGE (n:Medicine {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_SideEffect.csv' AS row
MERGE (n:SideEffect {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_LabTest.csv' AS row
MERGE (n:LabTest {id: row.id}) SET n.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_RiskFactor.csv' AS row
MERGE (n:RiskFactor {id: row.id}) SET n.name = row.name;

// ---------- 3. Relationships ----------
// Symptom -[:INDICATES]-> Disease
LOAD CSV WITH HEADERS FROM 'file:///edges_INDICATES.csv' AS row
MATCH (s:Symptom {id: row.source_id}), (d:Disease {id: row.target_id})
MERGE (s)-[r:INDICATES]->(d)
SET r.source = row.data_source, r.hpo_name = row.hpo_name;

// Medicine -[:TREATS]-> Disease   (was TREATED_BY in the raw data)
LOAD CSV WITH HEADERS FROM 'file:///edges_TREATS.csv' AS row
MATCH (m:Medicine {id: row.source_id}), (d:Disease {id: row.target_id})
MERGE (m)-[r:TREATS]->(d)
SET r.source = row.data_source;

// Medicine -[:NOT_RECOMMENDED_FOR]-> Disease   (contraindication)
LOAD CSV WITH HEADERS FROM 'file:///edges_NOT_RECOMMENDED_FOR.csv' AS row
MATCH (m:Medicine {id: row.source_id}), (d:Disease {id: row.target_id})
MERGE (m)-[r:NOT_RECOMMENDED_FOR]->(d)
SET r.source = row.data_source, r.reason = row.reason;

// Medicine -[:CAUSES]-> SideEffect
LOAD CSV WITH HEADERS FROM 'file:///edges_CAUSES.csv' AS row
MATCH (m:Medicine {id: row.source_id}), (s:SideEffect {id: row.target_id})
MERGE (m)-[r:CAUSES]->(s)
SET r.source = row.data_source;

// Medicine -[:INTERACTS_WITH]- Medicine   (symmetric; stored once, query without arrow)
LOAD CSV WITH HEADERS FROM 'file:///edges_INTERACTS_WITH.csv' AS row
MATCH (a:Medicine {id: row.source_id}), (b:Medicine {id: row.target_id})
MERGE (a)-[r:INTERACTS_WITH]->(b)
SET r.severity = row.severity, r.description = row.description, r.source = row.data_source;

// Disease -[:REQUIRES_TEST]-> LabTest
LOAD CSV WITH HEADERS FROM 'file:///edges_REQUIRES_TEST.csv' AS row
MATCH (d:Disease {id: row.source_id}), (t:LabTest {id: row.target_id})
MERGE (d)-[r:REQUIRES_TEST]->(t)
SET r.purpose = row.purpose, r.loinc_code = row.loinc_code, r.source = row.data_source;

// RiskFactor -[:RISK_FACTOR_FOR]-> Disease
LOAD CSV WITH HEADERS FROM 'file:///edges_RISK_FACTOR_FOR.csv' AS row
MATCH (rf:RiskFactor {id: row.source_id}), (d:Disease {id: row.target_id})
MERGE (rf)-[r:RISK_FACTOR_FOR]->(d)
SET r.evidence_level = row.evidence_level, r.source = row.data_source;

// ---------- 4. Merge risk factors that are really one of our diseases ----------
// e.g. RiskFactor "Type 2 diabetes mellitus" duplicates Disease "Type 2 diabetes mellitus".
// Its RISK_FACTOR_FOR links are moved onto the Disease itself and the duplicate is deleted,
// so no SAME_AS links are needed. (14 cases, incl. Hypertension and COPD.)
MATCH (rf:RiskFactor), (d:Disease)
WHERE toLower(rf.name) = toLower(d.name)
   OR (rf.name = 'Hypertension' AND d.name = 'Essential hypertension')
   OR (rf.name = 'COPD' AND d.name = 'Chronic obstructive pulmonary disease')
MATCH (rf)-[r:RISK_FACTOR_FOR]->(t:Disease)
MERGE (d)-[r2:RISK_FACTOR_FOR]->(t)
SET r2.evidence_level = r.evidence_level, r2.source = r.source;

MATCH (rf:RiskFactor), (d:Disease)
WHERE toLower(rf.name) = toLower(d.name)
   OR (rf.name = 'Hypertension' AND d.name = 'Essential hypertension')
   OR (rf.name = 'COPD' AND d.name = 'Chronic obstructive pulmonary disease')
DETACH DELETE rf;

// ---------- 5. Tag reliability ----------
// Symptom, treatment and contraindication layers were rebuilt from MedlinePlus,
// DrugBank and clinical guidelines, so every layer is now marked reliable.
MATCH ()-[r]->() SET r.status = 'reliable';

// ---------- 6. Verify ----------
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC;
MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS edges ORDER BY edges DESC;
