import os, json

def append_jsonl(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def load_existing_emails(path: str) -> set[str]:
    s: set[str] = set()
    if not os.path.exists(path):
        return s
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                e = obj.get("email")
                if isinstance(e, str):
                    s.add(e)
            except json.JSONDecodeError:
                pass
    return s

def tail_jsonl(path: str, limit: int) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-limit:]
    rows: list[dict] = []
    for ln in lines:
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows
