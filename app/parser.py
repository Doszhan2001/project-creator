# app/parser.py
from pathlib import Path
import re

# строки, состоящие только из графики/пробелов
DRAWING_ONLY_RE = re.compile(r'^[\s│├└┘┐┌─┬┴┤]+$')
# префикс (графика + пробелы) и остальное имя
LINE_RE = re.compile(r'^(?P<prefix>[\s│├└┘┐┌─┬┴┤]*)(?P<name>.+)$')


def parse_architecture(text: str):
    """
    Возвращает список словарей {"path": Path(...), "is_dir": bool}.
    Работает с ascii-деревом из твоего примера.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    entries = []
    stack = []  # (depth:int, path_str)

    for raw in lines:
        if not raw.strip():
            continue
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue

        # пропускаем строки, которые содержат только графические символы
        if DRAWING_ONLY_RE.fullmatch(line.strip()):
            continue

        m = LINE_RE.match(line)
        prefix = m.group("prefix") if m else ""
        name = (m.group("name").strip() if m else line.strip())

        if DRAWING_ONLY_RE.fullmatch(name):
            continue

        # нормализуем табы в 4 пробела
        prefix_expanded = prefix.replace("\t", "    ")

        # придумал простую эвристику глубины:
        # считаем сколько «боксовых» символов и сколько полных групп из 4 пробелов
        box_chars = sum(prefix_expanded.count(ch) for ch in "│├└┘┐┌─┬┴┤")
        leading_spaces = len(prefix_expanded) - sum(prefix_expanded.count(ch) for ch in "│├└┘┐┌─┬┴┤")
        depth = box_chars + (leading_spaces // 4)

        is_dir = name.endswith("/")
        norm = name.rstrip("/")

        # нормализуем обратные слэши (windows) -> unix style for internal logic
        norm = norm.replace("\\", "/")

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            parent = Path(stack[-1][1])
            path = parent / norm
        else:
            path = Path(norm)

        entries.append({"path": path, "is_dir": is_dir})

        if is_dir:
            stack.append((depth, str(path)))

    return entries


# быстрый тест (локально)
if __name__ == "__main__":
    sample = """page_builder/
│── app/
│   ├── main.py
│   ├── export_utils.py
│   ├── config.py
│   ├── templates/
│   │   ├── base.html
│   │   └── editor.html
│   └── static/
│       ├── js/
│       │   └── editor.js
│       └── css/
│           └── style.css
│
├── requirements.txt
└── run.sh
"""
    for e in parse_architecture(sample):
        print(e["path"], "dir" if e["is_dir"] else "file")
