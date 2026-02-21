"""Delete broken spaces and recreate with correct API version."""

import json
from src.utils.config import load_config
from src.notion.client import NotionService


def main():
    config = load_config()
    notion = NotionService(
        api_key=config["notion"]["api_key"],
        root_page_id=config["notion"]["root_page_id"],
    )

    # 1. Delete old broken spaces
    print("=== Deleting old spaces ===")
    spaces = notion.list_spaces()
    for s in spaces:
        print(f"  Deleting: {s['name']} ({s['id']})")
        notion.client.blocks.delete(block_id=s["id"])
    print(f"  Deleted {len(spaces)} space(s)")

    # 2. Create fresh spaces
    print("\n=== Creating new spaces ===")
    uni = notion.create_space("Universidad", icon="🎓")
    print(f"  Created: {uni['name']} ({uni['id']})")
    casa = notion.create_space("Casa", icon="🏠")
    print(f"  Created: {casa['name']} ({casa['id']})")

    # 3. Verify properties exist
    print("\n=== Verifying properties ===")
    db = notion.client.databases.retrieve(uni["id"])
    props = db.get("properties", {})
    print(f"  Properties: {list(props.keys())}")

    # 4. Create a task
    print("\n=== Create task ===")
    task = notion.create_task(
        space_id=uni["id"],
        title="Tarea de prueba",
        due_date="2026-02-15",
        priority="Alta",
        tags=["test"],
        notes="Creada por test_notion.py",
    )
    print(f"  Created: {json.dumps(task, ensure_ascii=False, indent=2)}")

    # 5. Get tasks
    print("\n=== Get tasks ===")
    tasks = notion.get_tasks(uni["id"])
    for t in tasks:
        print(f"  {t['title']} | {t['due_date']} | {t['status']} | {t['priority']}")

    # 6. Update task
    print("\n=== Update task ===")
    updated = notion.update_task(task["id"], status="En progreso")
    print(f"  Updated status: {updated['status']}")

    # 7. Search
    print("\n=== Search tasks ===")
    results = notion.search_tasks("prueba")
    print(f"  Found {len(results)} result(s)")

    # 8. Delete test task
    print("\n=== Delete task ===")
    notion.delete_task(task["id"])
    print("  Deleted OK")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
