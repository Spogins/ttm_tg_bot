venv:
	source .venv/bin/activate

run:
	python main.py

structure:
	find . -not -path './.venv/*' -not -path './.git/*' -not -path './.idea/*' | python3 -c "import sys, json paths = [l.strip() for l in sys.stdin if l.strip()] print(json.dumps(paths, indent=2))" > structure.json

