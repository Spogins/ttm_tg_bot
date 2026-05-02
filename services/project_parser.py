"""
Parse project structure files (JSON tree, TXT tree, or free-text description) into a ParsedProject.
"""
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

# matches top-level django app dirs: exactly one path segment before /apps.py
DJANGO_APP_PATTERN = re.compile(r"^[^/]+/apps\.py$")
# matches common fastapi router file naming conventions
FASTAPI_ROUTER_PATTERN = re.compile(r"router|routers|routes", re.IGNORECASE)


@dataclass
class ParsedProject:
    """
    Normalized output of any parse path: file list, tech stack, modules, and raw input.
    """
    files: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _collect_paths(node, prefix: str, paths: list[str]) -> None:
    """
    Recursively walk a nested dict/list structure and append all leaf paths.

    :param node: Current node — dict, list, or scalar.
    :param prefix: Accumulated path prefix for the current depth.
    :param paths: List to which discovered paths are appended in place.
    :return: None
    """
    if isinstance(node, dict):
        for key, value in node.items():
            # lstrip removes leading slash at root; replace("//", "/") prevents double-slash artifacts
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
    """
    Match filenames against TECH_MARKERS and return a sorted list of detected technologies.

    :param files: List of file paths from the project structure.
    :return: Sorted list of detected technology names.
    """
    tech: set[str] = set()
    for f in files:
        name = PurePath(f).name
        if name in TECH_MARKERS:
            tech.add(TECH_MARKERS[name])
    return sorted(tech)


def _detect_modules(files: list[str]) -> list[str]:
    """
    Detect Django app directories and FastAPI router modules from the file list.

    :param files: List of file paths from the project structure.
    :return: Sorted list of detected module names.
    """
    modules: set[str] = set()

    # django apps
    for f in files:
        if DJANGO_APP_PATTERN.match(f):
            modules.add(PurePath(f).parts[0])

    # fastapi routers
    for f in files:
        if FASTAPI_ROUTER_PATTERN.search(PurePath(f).stem):
            modules.add(PurePath(f).stem)

    return sorted(modules)


def _parse_txt_paths(text: str) -> list[str]:
    """
    Strip ASCII-tree characters from each line and return clean file paths.

    :param text: Raw text containing an ASCII file tree (│├└─ characters).
    :return: List of cleaned path strings.
    """
    paths = []
    for line in text.splitlines():
        line = re.sub(r"[│├└─\s]+", " ", line).strip()
        if line and not line.startswith("#"):
            paths.append(line)
    return paths


def parse_json(data: dict | list) -> ParsedProject:
    """
    Parse a JSON file-tree dict or list into a ParsedProject.

    :param data: Parsed JSON object representing the project file tree.
    :return: ParsedProject with detected files, tech stack, and modules.
    """
    files: list[str] = []
    _collect_paths(data, "", files)
    tech = _detect_tech(files)
    modules = _detect_modules(files)
    raw = data if isinstance(data, dict) else {"files": data}  # wrap list input so raw is always a dict
    return ParsedProject(files=files, tech_stack=tech, modules=modules, raw=raw)


def parse_txt(text: str) -> ParsedProject:
    """
    Parse an ASCII file-tree text block into a ParsedProject.

    :param text: Raw ASCII tree string (with │├└─ drawing characters).
    :return: ParsedProject with detected files, tech stack, and modules.
    """
    files = _parse_txt_paths(text)
    tech = _detect_tech(files)
    modules = _detect_modules(files)
    return ParsedProject(files=files, tech_stack=tech, modules=modules, raw={"raw_text": text})


def parse_text_description(text: str) -> ParsedProject:
    """
    Extract known technology names from a free-form text description.

    :param text: Free-form user text describing the project.
    :return: ParsedProject with detected tech stack; files and modules are empty.
    """
    known_tech = list(TECH_MARKERS.values()) + [
        "FastAPI", "Flask", "Django", "React", "Vue", "Angular",
        "PostgreSQL", "MongoDB", "Redis", "Kafka", "RabbitMQ",
    ]
    # word boundaries (\b) prevent partial matches, e.g. "Go" matching inside "MongoDB"
    found = [t for t in known_tech if re.search(rf"\b{re.escape(t)}\b", text, re.IGNORECASE)]
    tech = sorted(set(found))
    return ParsedProject(files=[], tech_stack=tech, modules=[], raw={"description": text})


def parse(content: str | bytes) -> ParsedProject:
    """
    Auto-detect content format (JSON, ASCII tree, or free text) and delegate to the right parser.

    :param content: Raw file bytes or text string from the user upload.
    :return: ParsedProject produced by the appropriate sub-parser.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    # try JSON first (most structured input)
    try:
        data = json.loads(content)
        return parse_json(data)
    except (json.JSONDecodeError, ValueError):
        pass

    # heuristic: ASCII tree characters or many slashes suggest a file-tree text dump
    if any(c in content for c in ["│", "├", "└", "─"]) or content.count("/") > 3:
        return parse_txt(content)

    # fall back to free-text tech detection
    return parse_text_description(content)
