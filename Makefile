venv:
	source .venv/bin/activate

run:
	python main.py

structure:
	find . -not -path './.venv/*' -not -path './.git/*' -not -path './.idea/*' | python3 -c "import sys, json paths = [l.strip() for l in sys.stdin if l.strip()] print(json.dumps(paths, indent=2))" > structure.json

.PHONY: migrate migrations

migrate:
	python scripts/migrate.py

migrations:
	@test -n "$(name)" || (echo "Usage: make migrations name=<migration_name>"; exit 1)
	python scripts/migrate.py --create $(name)
