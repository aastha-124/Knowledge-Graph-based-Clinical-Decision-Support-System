# Minimal context pipeline

question → scispaCy entities → most similar graph nodes → facts from Neo4j → prompt (→ model later)

## Files
- `kg_context.py` – the whole pipeline (one file)
- `synonyms.csv` – stored keywords: every node's name + synonyms + everyday words (1,883 terms, 715 nodes)
- `build_synonyms.py` – rebuilds `synonyms.csv` if the graph changes (expects `../neo4j_import/`)

## Setup (once, in a fresh Python environment)
```
pip install scispacy rapidfuzz neo4j pandas
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz
```
If the model install fails, check the scispaCy GitHub page for the model link that matches your scispaCy version.
Without the model the script still runs, using the keyword scan only.

## Run (Neo4j running with the graph loaded)
```
export NEO4J_PASSWORD=yourpassword        # Windows: set NEO4J_PASSWORD=yourpassword
python kg_context.py "Can I take Tylenol with high BP?"
```
Next semester, with Ollama installed: `python kg_context.py --ollama=llama3.2 "..."`

## Settings
- `THRESHOLD = 85` in `kg_context.py`: how similar an entity and a keyword must be (0–100).
