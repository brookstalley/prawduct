import ast, pathlib, re, sys, collections
root = pathlib.Path('.')
files = [p for p in root.glob('plugin/skills/**/*.md') if '/critic/' not in str(p) and '/pr/' not in str(p)]
texts = {str(p): p.read_text() for p in files}
norm = {k: re.sub(r'\s+', ' ', v) for k, v in texts.items()}
out = collections.defaultdict(set)
for t in root.glob('tests/**/*.py'):
    try:
        tree = ast.parse(t.read_text())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if len(s) < 10 or len(s) > 200 or '\n' in s.strip(): continue
            ns = re.sub(r'\s+', ' ', s)
            for f, txt in norm.items():
                if ns in txt:
                    out[f].add((str(t), s))
for f in sorted(out):
    print('=== ', f)
    for t, s in sorted(out[f], key=lambda x: x[1]):
        print(f'   {t.split("/")[-1]}: {s!r}')
