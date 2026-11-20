"""Parse hp.obo into name/synonym -> (id, official name) lookup."""
import re
def load(path):
    terms, cur = {}, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line == "[Term]": cur = {"syn": []}; continue
        if line.startswith("[") : cur = None; continue
        if cur is None: continue
        if line.startswith("id: "): cur["id"] = line[4:]; terms[cur["id"]] = cur
        elif line.startswith("name: "): cur["name"] = line[6:]
        elif line.startswith("is_obsolete: true"): cur["obs"] = True
        elif line.startswith("synonym: "):
            m = re.match(r'synonym: "(.*)" (EXACT|RELATED|BROAD|NARROW)', line)
            if m: cur["syn"].append((m.group(1), m.group(2)))
    exact, related = {}, {}
    for t in terms.values():
        if t.get("obs") or "name" not in t: continue
        exact.setdefault(t["name"].lower(), (t["id"], t["name"]))
        for s, k in t["syn"]:
            (exact if k == "EXACT" else related).setdefault(s.lower(), (t["id"], t["name"]))
    return terms, exact, related
