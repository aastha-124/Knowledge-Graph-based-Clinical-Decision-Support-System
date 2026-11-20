"""
Minimal pipeline:  question -> entities -> similar graph nodes -> facts from Neo4j -> prompt -> model

  1. extract_entities()  scispaCy finds medical entity names in the question
  2. match_nodes()       compare each entity with every node name + synonym (synonyms.csv), keep the most similar
  3. get_facts()         fetch the facts around the matched nodes from Neo4j
  4. build_prompt()      facts + question + rules
  5. ask_model()         (optional) send the prompt to a local Ollama model

Setup:   pip install scispacy rapidfuzz neo4j pandas  (+ the en_ner_bc5cdr_md model, see README)
Run:     python kg_context.py "Can I take Tylenol with high BP?"
         python kg_context.py --ollama=llama3.2 "Can I take Tylenol with high BP?"
"""
import json, os, re, sys, urllib.request
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz

HERE = Path(__file__).resolve().parent
THRESHOLD = 85          # how similar (0-100) an entity and a node name must be to count as a match


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("'", "")).strip()


# ---------------------------------------------------------------- the stored keywords (one row per way of writing a node)
SYN = pd.read_csv(HERE / "synonyms.csv", dtype=str)            # node_id, label, name, term
TERMS = SYN.groupby("term")[["node_id", "label", "name"]].apply(lambda g: g.to_dict("records")).to_dict()
PRIORITY = {"Disease": 0, "Medicine": 1, "Symptom": 2, "LabTest": 3, "RiskFactor": 4, "SideEffect": 5}


# ---------------------------------------------------------------- 1. entities from the question
def load_nlp():
    try:
        import spacy
        return spacy.load("en_ner_bc5cdr_md")                   # scispaCy model: DISEASE and CHEMICAL
    except Exception:
        print("(scispaCy model not found: using keyword scan only)")
        return None


def extract_entities(question, nlp):
    ents = [e.text for e in nlp(question).ents] if nlp else []
    # also scan for stored keywords, which catches everyday words scispaCy misses ("high bp", "tylenol")
    words = norm(question).split()
    for n in range(4, 0, -1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            if phrase in TERMS and not any(phrase in norm(e) for e in ents):
                ents.append(phrase)
    return ents


# ---------------------------------------------------------------- 2. entity <-> node similarity
def match_nodes(entities):
    matched = {}
    for ent in entities:
        e = norm(ent)
        if e in TERMS:                                           # exact keyword: similarity 100
            term, score = e, 100
        else:                                                    # otherwise the most similar keyword
            best = process.extractOne(e, TERMS.keys(), scorer=fuzz.WRatio, score_cutoff=THRESHOLD)
            if not best or len(e) < 4:
                continue
            term, score, _ = best
        nodes = sorted(TERMS[term], key=lambda n: PRIORITY[n["label"]])
        node = nodes[0]                                          # same word, several nodes -> disease first
        key = (node["node_id"], node["label"])
        if key not in matched or score > matched[key]["score"]:
            matched[key] = dict(node, entity=ent, score=round(score))
    return list(matched.values())


# ---------------------------------------------------------------- 3. facts around the matched nodes
CYPHER = """
MATCH (n {id: $id})-[r]-(m) WHERE $label IN labels(n)
RETURN type(r) AS rel, startNode(r).name AS src, endNode(r).name AS dst,
       coalesce(r.reason, r.purpose, r.evidence_level, r.severity + ': ' + r.description, '') AS detail,
       r.source AS source
ORDER BY CASE type(r) WHEN 'CAUSES' THEN 1 ELSE 0 END      // side effects last, so they never push out the rest
LIMIT 40
"""


def get_facts(nodes):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                                  auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")))
    facts = []
    with driver.session() as s:
        for n in nodes:
            facts += [r.data() for r in s.run(CYPHER, id=n["node_id"], label=n["label"])]
    driver.close()
    return list({(f["rel"], f["src"], f["dst"]): f for f in facts}.values())   # drop duplicates


# ---------------------------------------------------------------- 4. prompt
SENTENCE = {
    "TREATS": "{src} is used to treat {dst}.",
    "NOT_RECOMMENDED_FOR": "{src} is NOT recommended for {dst}: {detail}.",
    "INDICATES": "{src} is a symptom of {dst}.",
    "RISK_FACTOR_FOR": "{src} is a {detail} risk factor for {dst}.",
    "REQUIRES_TEST": "{src} is checked with the {dst} test ({detail}).",
    "CAUSES": "{src} can cause {dst}.",
    "INTERACTS_WITH": "{src} interacts with {dst} ({detail}).",
}


def build_prompt(question, facts):
    if not facts:
        return None
    lines = [f"- {SENTENCE[f['rel']].format(**f)} (Source: {f['source']})" for f in facts]
    return ("You are a medical information assistant.\n\nFacts from the knowledge graph:\n" + "\n".join(lines) +
            f"\n\nQuestion: {question}\n\n"
                        "Answer the question in 3 to 5 short sentences, using ONLY the facts above. "
            "Use only the facts that answer the question and ignore all other facts. "
            "Always include any warning or drug interaction that affects the person asking. "
            "Do not add information that is not in the facts, and do not contradict yourself. "
            "Use simple everyday words and explain any medical term in brackets "
            "(e.g. bronchospasm = narrowing of the airways). If the facts do not answer the question, "
            "say so. Do not diagnose. Always end with this exact sentence: "
            "Please consult a doctor or pharmacist.")


# ---------------------------------------------------------------- 5. model (optional, next step)
def ask_model(prompt, model="llama3.2"):
    req = urllib.request.Request("http://localhost:11434/api/generate",
                                 data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["response"]


if __name__ == "__main__":
    question = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "Can I take Tylenol with high BP?"
    ents = extract_entities(question, load_nlp())
    nodes = match_nodes(ents)
    print("Entities:", ents)
    print("Matched nodes:", [f"{n['name']} ({n['label']}, {n['score']}%)" for n in nodes])
    prompt = build_prompt(question, get_facts(nodes)) if nodes else None
    print("\n" + (prompt or "Not covered in the knowledge base."))
    model = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--ollama=")), None)
    if model and prompt:
        print("\nModel answer:\n" + ask_model(prompt, model))
