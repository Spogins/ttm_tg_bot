"""
Usage:
  python scripts/migrate.py           — run pending migrations
  python scripts/migrate.py --create name_of_migration
"""
import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.mongodb.client import connect, get_database


async def run_migrations():
    await connect()
    db = get_database()
    applied = {
        doc["name"]
        async for doc in db["_migrations"].find({}, {"name": 1})
    }

    migration_files = sorted(Path("migrations").glob("*.py"))
    pending = [f for f in migration_files if f.stem not in applied]

    if not pending:
        print("No pending migrations.")
        return

    for path in pending:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        print(f"Applying {path.stem}: {module.description}")
        await module.up(db)
        await db["_migrations"].insert_one({
            "name": path.stem,
            "applied_at": datetime.now(timezone.utc),
        })
        print(f"  Done.")


def create_migration(name: str):
    Path("migrations").mkdir(exist_ok=True)
    existing = sorted(Path("migrations").glob("*.py"))
    next_num = len(existing) + 1
    filename = f"migrations/{next_num:03d}_{name}.py"
    Path(filename).write_text(
        f'description = "{name}"\n\n\nasync def up(db):\n    pass\n'
    )
    print(f"Created: {filename}")


if __name__ == "__main__":
    if "--create" in sys.argv:
        idx = sys.argv.index("--create")
        if idx + 1 >= len(sys.argv) or not sys.argv[idx + 1]:
            print("Usage: python scripts/migrate.py --create <name>")
            sys.exit(1)
        create_migration(sys.argv[idx + 1])
    else:
        asyncio.run(run_migrations())
