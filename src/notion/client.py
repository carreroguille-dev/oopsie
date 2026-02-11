"""Notion service layer — wraps notion-client SDK for Oopsie domain operations.

IMPORTANT: We pin notion_version='2022-06-28' because the default version
in notion-client 2.7.0 (2025-09-03) does NOT return database properties
and silently ignores property updates. The 2022-06-28 API is the stable
version where database properties work correctly.
"""

from notion_client import Client

# Stable API version that supports database properties
NOTION_API_VERSION = "2022-06-28"

# Schema constants matching SCHEMA.md
TASK_DB_PROPERTIES = {
    "Título": {"title": {}},
    "Fecha de vencimiento": {"date": {}},
    "Estado": {
        "select": {
            "options": [
                {"name": "Pendiente", "color": "default"},
                {"name": "En progreso", "color": "blue"},
                {"name": "Completada", "color": "green"},
            ]
        }
    },
    "Prioridad": {
        "select": {
            "options": [
                {"name": "Baja", "color": "gray"},
                {"name": "Media", "color": "yellow"},
                {"name": "Alta", "color": "orange"},
                {"name": "Urgente", "color": "red"},
            ]
        }
    },
    "Etiquetas": {"multi_select": {"options": []}},
    "Enlaces": {"url": {}},
    "Notas": {"rich_text": {}},
}


class NotionService:
    def __init__(self, api_key: str, root_page_id: str):
        self.client = Client(auth=api_key, notion_version=NOTION_API_VERSION)
        self.root_page_id = root_page_id

    # --- Spaces (each space = a database under the root page) ---

    def list_spaces(self) -> list[dict]:
        """List all space databases under the root page."""
        children = self.client.blocks.children.list(self.root_page_id)
        spaces = []
        for block in children["results"]:
            if block["type"] == "child_database":
                spaces.append({
                    "id": block["id"],
                    "name": block["child_database"]["title"],
                })
        return spaces

    def create_space(self, name: str, icon: str = "📁") -> dict:
        """Create a new space (database with task schema) under the root page.

        Uses client.request() because the high-level databases.create()
        strips the properties kwarg from the request body.
        """
        db = self.client.request(
            path="databases",
            method="POST",
            body={
                "parent": {"type": "page_id", "page_id": self.root_page_id},
                "title": [{"type": "text", "text": {"content": name}}],
                "icon": {"type": "emoji", "emoji": icon},
                "properties": TASK_DB_PROPERTIES,
            },
        )
        return {"id": db["id"], "name": name}

    def ensure_space_properties(self, space_id: str) -> None:
        """Ensure a database has all required task properties.

        Fixes databases that were created under the broken 2025-09-03 API
        which silently ignored properties. Also renames the default 'Name'
        title property to 'Título' if needed.
        """
        db = self.client.databases.retrieve(space_id)
        existing = db.get("properties", {})
        existing_names = set(existing.keys())

        updates = {}

        # Rename default "Name" title property to "Título"
        if "Name" in existing_names and "Título" not in existing_names:
            updates["Name"] = {"name": "Título", "title": {}}

        # Add all other missing non-title properties
        for prop_name, prop_schema in TASK_DB_PROPERTIES.items():
            if prop_name not in existing_names and prop_name != "Título":
                updates[prop_name] = prop_schema

        if updates:
            self.client.databases.update(
                database_id=space_id, properties=updates
            )

    # --- Tasks (entries in a space database) ---

    def get_tasks(self, space_id: str, status: str | None = None,
                  fecha_inicio: str | None = None,
                  fecha_fin: str | None = None) -> list[dict]:
        """Get tasks from a space, optionally filtered by status and/or date range.

        Uses client.request() because databases.query() doesn't exist in
        notion-client 2.7.0.

        Args:
            space_id: Database UUID.
            status: Filter by status value (e.g. "Pendiente").
            fecha_inicio: Start date (YYYY-MM-DD). Only tasks on or after this date.
            fecha_fin: End date (YYYY-MM-DD). Only tasks on or before this date.
        """
        filters: list[dict] = []

        if status:
            filters.append({"property": "Estado", "select": {"equals": status}})
        if fecha_inicio:
            filters.append({"property": "Fecha de vencimiento", "date": {"on_or_after": fecha_inicio}})
        if fecha_fin:
            filters.append({"property": "Fecha de vencimiento", "date": {"on_or_before": fecha_fin}})

        body = {}
        if len(filters) == 1:
            body["filter"] = filters[0]
        elif len(filters) > 1:
            body["filter"] = {"and": filters}

        response = self.client.request(
            path=f"databases/{space_id}/query",
            method="POST",
            body=body,
        )
        return [self._parse_task(page) for page in response["results"]]

    def create_task(self, space_id: str, title: str, due_date: str | None = None,
                    priority: str = "Media", tags: list[str] | None = None,
                    notes: str | None = None, url: str | None = None) -> dict:
        """Create a task in a space."""
        properties = {
            "Título": {"title": [{"text": {"content": title}}]},
            "Estado": {"select": {"name": "Pendiente"}},
            "Prioridad": {"select": {"name": priority}},
        }
        if due_date:
            properties["Fecha de vencimiento"] = {"date": {"start": due_date}}
        if tags:
            properties["Etiquetas"] = {"multi_select": [{"name": t} for t in tags]}
        if notes:
            properties["Notas"] = {"rich_text": [{"text": {"content": notes}}]}
        if url:
            properties["Enlaces"] = {"url": url}

        page = self.client.pages.create(
            parent={"database_id": space_id},
            properties=properties,
        )
        return self._parse_task(page)

    def update_task(self, task_id: str, **updates) -> dict:
        """Update task properties. Accepts: title, due_date, status, priority, tags, notes, url."""
        properties = {}
        if "title" in updates:
            properties["Título"] = {"title": [{"text": {"content": updates["title"]}}]}
        if "due_date" in updates:
            properties["Fecha de vencimiento"] = {"date": {"start": updates["due_date"]} if updates["due_date"] else None}
        if "status" in updates:
            properties["Estado"] = {"select": {"name": updates["status"]}}
        if "priority" in updates:
            properties["Prioridad"] = {"select": {"name": updates["priority"]}}
        if "tags" in updates:
            properties["Etiquetas"] = {"multi_select": [{"name": t} for t in updates["tags"]]}
        if "notes" in updates:
            properties["Notas"] = {"rich_text": [{"text": {"content": updates["notes"]}}]}
        if "url" in updates:
            properties["Enlaces"] = {"url": updates["url"]}

        page = self.client.pages.update(page_id=task_id, properties=properties)
        return self._parse_task(page)

    def delete_task(self, task_id: str) -> bool:
        """Archive (delete) a task."""
        self.client.pages.update(page_id=task_id, archived=True)
        return True

    def search_tasks(self, query: str) -> list[dict]:
        """Search tasks across all spaces."""
        response = self.client.search(
            query=query,
            filter={"property": "object", "value": "page"},
        )
        tasks = []
        for page in response["results"]:
            if page.get("parent", {}).get("type") == "database_id":
                try:
                    tasks.append(self._parse_task(page))
                except (KeyError, IndexError):
                    continue
        return tasks

    # --- Helpers ---

    def _parse_task(self, page: dict) -> dict:
        """Extract clean task dict from a Notion page object."""
        props = page["properties"]
        title_list = props.get("Título", {}).get("title", [])
        date_obj = props.get("Fecha de vencimiento", {}).get("date")
        status_obj = props.get("Estado", {}).get("select")
        priority_obj = props.get("Prioridad", {}).get("select")
        tags_list = props.get("Etiquetas", {}).get("multi_select", [])
        notes_list = props.get("Notas", {}).get("rich_text", [])
        url_val = props.get("Enlaces", {}).get("url")

        return {
            "id": page["id"],
            "title": title_list[0]["text"]["content"] if title_list else "",
            "due_date": self._format_date(date_obj["start"]) if date_obj else None,
            "status": status_obj["name"] if status_obj else "Pendiente",
            "priority": priority_obj["name"] if priority_obj else "Media",
            "tags": [t["name"] for t in tags_list],
            "notes": notes_list[0]["text"]["content"] if notes_list else "",
            "url": url_val,
        }

    @staticmethod
    def _format_date(iso_date: str) -> str:
        """Convert YYYY-MM-DD to DD/MM/YYYY for display."""
        parts = iso_date.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return iso_date
