venv:
	source .venv/bin/activate

run:
	python main.py

structure:
	python3 -c "\
import json, subprocess, re, os; \
find_cmd = 'find . -name \"*.py\" -not -path \"./.venv/*\" -not -path \"./.env/*\" -not -path \"*/__pycache__/*\" -not -path \"./.git/*\" -not -path \"./.idea/*\" -not -path \"./node_modules/*\"'; \
files = sorted(f[2:] for f in subprocess.check_output(find_cmd, shell=True).decode().split() if f.strip()); \
dep = next((f for f in ['requirements.txt', 'requirements-dev.txt', 'requirements/base.txt', 'Pipfile', 'setup.cfg'] if os.path.exists(f)), None); \
tech = sorted(set(re.split(r'[~>=<!]', l)[0].split('[')[0].strip() for l in open(dep) if l.strip() and not l.startswith(('#', '-', '[')))) if dep else []; \
print(json.dumps({'tech_stack': tech, 'files': files}, indent=2))" > structure.json

.PHONY: migrate migrations docker-build docker-up docker-down docker-logs docker-restart docker-migrate docker-shell docker-clean

migrate:
	python scripts/migrate.py

migrations:
	@test -n "$(name)" || (echo "Usage: make migrations name=<migration_name>"; exit 1)
	python scripts/migrate.py --create $(name)

# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f bot

docker-restart:
	docker compose restart bot

docker-migrate:
	docker compose exec bot python scripts/migrate.py

docker-shell:
	docker compose exec bot bash

docker-clean:
	docker compose down -v --remove-orphans

docker-run:
	docker compose up -d --build bot

docker-stop:
	docker compose stop bot
