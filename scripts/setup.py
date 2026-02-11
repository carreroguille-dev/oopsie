"""Setup script for Oopsie.

Verifies Notion API connection and that the root page is accessible.

Prerequisites:
  1. Create a page in Notion (this will be Oopsie Hub)
  2. Share that page with your Notion integration
  3. Copy the page ID to NOTION_ROOT_PAGE_ID in .env
"""

from __future__ import annotations

import os
import sys

_DEPS_AVAILABLE = True
try:
    from dotenv import load_dotenv
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    _DEPS_AVAILABLE = False


def main():
    if not _DEPS_AVAILABLE:
        print("Missing dependencies. Install with: pip install -r requirements.txt")
        sys.exit(1)

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    load_dotenv(env_path)

    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print("ERROR: NOTION_API_KEY not found in .env")
        sys.exit(1)

    root_page_id = os.getenv("NOTION_ROOT_PAGE_ID")
    if not root_page_id:
        print("ERROR: NOTION_ROOT_PAGE_ID not found in .env")
        print()
        print("To fix this:")
        print("  1. Create a page in Notion (name it 'Oopsie Hub' or whatever you like)")
        print("  2. Share that page with your integration (... menu > Connections)")
        print("  3. Copy the page ID from the URL and paste it in .env")
        print("     Example URL: https://notion.so/My-Page-97cffaa61eda42cba84da22a6415efa8")
        print("     The ID is: 97cffaa61eda42cba84da22a6415efa8")
        sys.exit(1)

    client = Client(auth=api_key)

    # Step 1: Verify API connection
    print("Verifying Notion API connection...")
    try:
        client.users.me()
    except APIResponseError as e:
        print(f"ERROR: Could not connect to Notion API: {e}")
        sys.exit(1)
    print("  API connection OK.")

    # Step 2: Verify root page is accessible
    print(f"Verifying root page ({root_page_id})...")
    try:
        page = client.pages.retrieve(root_page_id)
        title_list = page.get("properties", {}).get("title", {}).get("title", [])
        title = title_list[0]["text"]["content"] if title_list else "(untitled)"
        print(f"  Root page found: '{title}'")
    except APIResponseError as e:
        print(f"ERROR: Could not access root page: {e}")
        print()
        print("Make sure you:")
        print("  1. Shared the page with your integration (... menu > Connections)")
        print("  2. Copied the correct page ID to NOTION_ROOT_PAGE_ID in .env")
        sys.exit(1)

    # Step 3: Check if spaces (databases) already exist
    children = client.blocks.children.list(root_page_id)
    db_count = sum(1 for b in children["results"] if b["type"] == "child_database")
    print(f"  Existing spaces: {db_count}")

    print()
    print("Setup complete! Everything looks good.")
    print("Run the app with: python -m src.main")


if __name__ == "__main__":
    main()
