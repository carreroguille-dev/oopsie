from __future__ import annotations

import argparse
import os
import sys

_DEPS_AVAILABLE = True
try:
    from dotenv import load_dotenv, set_key
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    _DEPS_AVAILABLE = False


def get_notion_client(api_key: str) -> Client:
    """Create and return a Notion client."""
    return Client(auth=api_key)


def verify_connection(client: Client) -> bool:
    """Verify that the Notion API key is valid."""
    try:
        client.users.me()
        return True
    except APIResponseError as e:
        print(f"Error connecting to Notion API: {e}")
        return False


def find_existing_hub(client: Client, root_page_id: str | None) -> str | None:
    """Check if an Oopsie Hub page already exists."""
    if root_page_id:
        try:
            page = client.pages.retrieve(root_page_id)
            title = page["properties"].get("title", {}).get("title", [])
            if title and "Oopsie Hub" in title[0].get("text", {}).get("content", ""):
                return root_page_id
        except APIResponseError:
            pass

    # Search by name
    try:
        results = client.search(
            query="Oopsie Hub",
            filter={"property": "object", "value": "page"},
        )
        for result in results.get("results", []):
            title_prop = result.get("properties", {}).get("title", {})
            title_list = title_prop.get("title", [])
            if title_list:
                content = title_list[0].get("text", {}).get("content", "")
                if content == "Oopsie Hub":
                    return result["id"]
    except APIResponseError:
        pass

    return None


def create_hub_page(client: Client) -> str:
    """Create the Oopsie Hub root page."""
    page = client.pages.create(
        parent={"type": "workspace", "workspace": True},
        properties={
            "title": [{"text": {"content": "Oopsie"}}],
        },
        icon={"type": "emoji", "emoji": "🐣"},
        children=[
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "👋"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Bienvenido a Oopsie"
                                "Aquí se organizarán tus espacios y tareas."
                            },
                        }
                    ],
                },
            }
        ],
    )
    return page["id"]


def save_page_id(page_id: str, env_path: str) -> None:
    """Save the root page ID to .env file."""
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("")
    set_key(env_path, "NOTION_ROOT_PAGE_ID", page_id)


def main():
    parser = argparse.ArgumentParser(
        description="Set up Oopsie Hub in Notion",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate Oopsie Hub even if it already exists",
    )
    args = parser.parse_args()

    if not _DEPS_AVAILABLE:
        print("Missing dependencies. Install with: pip install -r requirements.txt")
        sys.exit(1)

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    load_dotenv(env_path)

    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print("NOTION_API_KEY not found. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    client = get_notion_client(api_key)

    # Step 1: Verify connection
    print("Verifying Notion API connection...")
    if not verify_connection(client):
        print("Could not connect to Notion. Check your API key.")
        sys.exit(1)
    print("Connection OK.")

    # Step 2: Check for existing hub
    existing_id = os.getenv("NOTION_ROOT_PAGE_ID")
    hub_id = find_existing_hub(client, existing_id)

    if hub_id and not args.force:
        print(f"Oopsie Hub already exists (ID: {hub_id}).")
        print("Use --force to recreate.")
        save_page_id(hub_id, env_path)
        return

    # Step 3: Create hub page
    print("Creating Oopsie Hub page...")
    try:
        hub_id = create_hub_page(client)
    except APIResponseError as e:
        print(f"Error creating page: {e}")
        sys.exit(1)

    # Step 4: Save ID
    save_page_id(hub_id, env_path)
    print(f"Oopsie Hub created! (ID: {hub_id})")
    print(f"Page ID saved to {env_path}")
    print()
    print("Next steps:")
    print("  1. Open Notion and find the 'Oopsie Hub' page")
    print("  2. Share the page with your integration if needed")
    print("  3. Run the application: python -m src.interface.app")


if __name__ == "__main__":
    main()
