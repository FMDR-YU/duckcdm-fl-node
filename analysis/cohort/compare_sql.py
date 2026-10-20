"""Compare two SQL files ignoring whitespace differences. Usage: python cmp.py a.sql b.sql"""
import sys, re, difflib

def norm_lines(path):
    txt = open(path, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    out = []
    for ln in txt.split("\n"):
        s = re.sub(r"\s+", " ", ln).strip()
        if s:
            out.append(s)
    return out

a, b = norm_lines(sys.argv[1]), norm_lines(sys.argv[2])
if a == b:
    print("IDENTICAL (whitespace-normalized):", len(a), "non-blank lines")
    sys.exit(0)
diff = list(difflib.unified_diff(a, b, sys.argv[1].split("/")[-1], sys.argv[2].split("/")[-1], n=1, lineterm=""))
print(f"DIFFERENT: {len(a)} vs {len(b)} lines, {sum(1 for d in diff if d[:1] in '+-' and d[:3] not in ('+++','---'))} changed lines")
print("\n".join(diff[:120]))
sys.exit(1)
