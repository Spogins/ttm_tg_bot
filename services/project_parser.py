import json
import re
from dataclasses import dataclass, field
from pathlib import PurePath

TECH_MARKERS = {
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "package.json": "Node.js",
    "yarn.lock": "Node.js",
    "pnpm-lock.yaml": "Node.js",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java",
    "build.gradle": "Java",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "mix.exs": "Elixir",
    "docker-compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
    "Dockerfile": "Docker",
    "nginx.conf": "Nginx",
    "manage.py": "Django",
    "alembic.ini": "SQLAlchemy",
    "prisma": "Prisma",
}

DJANGO_APP_PATTERN = re.compile(r"^[^/]+/apps\.py$")
FASTAPI_ROUTER_PATTERN = re.compile(r"router|routers|routes", re.IGNORECASE)


@dataclass
class ParsedProject:
    files: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _collect_paths(node, prefix: str, paths: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            full = f"{prefix}/{key}".lstrip("/").replace("//", "/")
            paths.append(full)
            _collect_paths(value, full, paths)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                paths.append(f"{prefix}/{item}".lstrip("/").replace("//", "/"))
            else:
                _collect_paths(item, prefix, paths)


def _detect_tech(files: list[str]) -> list[str]:
    tech: set[str] = set()
    for f in files:
        name = PurePath(f).name
        if name in TECH_MARKERS:
            tech.add(TECH_MARKERS[name])
    return sorted(tech)


def _detect_modules(files: list[str]) -> list[str]:
    modules: set[str] = set()

    # Django apps
    for f in files:
        if DJANGO_APP_PATTERN.match(f):
            modules.add(PurePath(f).parts[0])

    # FastAPI routers
    for f in files:
        if FASTAPI_ROUTER_PATTERN.search(PurePath(f).stem):
            modules.add(PurePath(f).stem)

    return sorted(modules)


def _parse_txt_paths(text: str) -> list[str]:
    paths = []
    for line in text.splitlines():
        line = re.sub(r"[│├└─\s]+", " ", line).strip()
        if line and not line.startswith("#"):
            paths.append(line)
    return paths


def parse_json(data: dict | list) -> ParsedProject:
    files: list[str] = []
    _collect_paths(data, "", files)
    tech = _detect_tech(files)
    modules = _detect_modules(files)
    raw = data if isinstance(data, dict) else {"files": data}
    return ParsedProject(files=files, tech_stack=tech, modules=modules, raw=raw)


def parse_txt(text: str) -> ParsedProject:
    files = _parse_txt_paths(text)
    tech = _detect_tech(files)
    modules = _detect_modules(files)
    return ParsedProject(files=files, tech_stack=tech, modules=modules, raw={"raw_text": text})


def parse_text_description(text: str) -> ParsedProject:
    """Свободный текст от пользователя — пытаемся вычленить технологии."""
    known_tech = list(TECH_MARKERS.values()) + [
        "FastAPI", "Flask", "Django", "React", "Vue", "Angular",
        "PostgreSQL", "MongoDB", "Redis", "Kafka", "RabbitMQ",
    ]
    found = [t for t in known_tech if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)]
    tech = sorted(set(found))
    return ParsedProject(files=[], tech_stack=tech, modules=[], raw={"description": text})


def parse(content: str | bytes) -> ParsedProject:
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    # пробуем JSON
    try:
        data = json.loads(content)
        return parse_json(data)
    except (json.JSONDecodeError, ValueError):
        pass

    # если похоже на дерево файлов — TXT
    if any(c in content for c in ["│", "├", "└", "─"]) or content.count("/") > 3:
        return parse_txt(content)

    # иначе свободный текст
    return parse_text_description(content)
