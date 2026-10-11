import json

with open(r"C:\Users\mural\.gemini\antigravity-ide\brain\a5a5a29d-4419-4206-a564-69cc5ebac56a\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        if obj.get("type") == "USER_INPUT":
            with open("prompt.md", "w", encoding="utf-8") as out:
                out.write(obj["content"])
            break
