import calendar
import logging
from datetime import datetime

from notion_client import Client

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"

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
    "Fecha de finalización": {"date": {}},
    "Enlaces": {"url": {}},
    "Notas": {"rich_text": {}},
}


def _validate_date(date_str: str) -> str:
    """Validate and fix a YYYY-MM-DD date string. Clamps invalid days to the last valid day of the month."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        parts = date_str.split("-")
        if len(parts) == 3:
            year, month = int(parts[0]), int(parts[1])
            last_valid = calendar.monthrange(year, month)[1]
            fixed = f"{year:04d}-{month:02d}-{last_valid:02d}"
            logger.warning("Invalid date '%s' corrected to '%s'", date_str, fixed)
            return fixed
        raise ValueError(f"Invalid date format: {date_str}")


class NotionService:
    def __init__(self, api_key: str, root_page_id: str):
        logger.info("Initializing NotionService with root_page_id=%s, api_version=%s",
                   root_page_id[:8] + "...", NOTION_API_VERSION)
        self.client = Client(auth=api_key, notion_version=NOTION_API_VERSION)
        self.root_page_id = root_page_id
        logger.info("NotionService initialized successfully")

    # --- Spaces (each space = a database under the root page) ---

    def list_spaces(self) -> list[dict]:
        """List all space databases under the root page."""
        logger.debug("Fetching spaces from root_page_id=%s", self.root_page_id[:8] + "...")
        try:
            logger.debug("API call: GET blocks/%s/children", self.root_page_id)
            children = self.client.blocks.children.list(self.root_page_id)
            spaces = []
            for block in children["results"]:
                if block["type"] == "child_database":
                    spaces.append({
                        "id": block["id"],
                        "name": block["child_database"]["title"],
                    })
            logger.info("Found %d space(s)", len(spaces))
            return spaces
        except Exception as e:
            logger.error("Failed to list spaces (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

    def create_space(self, name: str, icon: str = "📁") -> dict:
        """Create a new space (database with task schema) under the root page.

        Uses client.request() because the high-level databases.create()
        strips the properties kwarg from the request body.
        """
        logger.info("Creating space with name='%s', icon='%s'", name, icon)
        try:
            logger.debug("API call: POST databases")
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
            logger.info("Space created successfully with id=%s", db["id"][:8] + "...")
            return {"id": db["id"], "name": name}
        except Exception as e:
            logger.error("Failed to create space '%s' (HTTP status=%s): %s", name, getattr(e, "status", None), e, exc_info=True)
            raise

    def ensure_space_properties(self, space_id: str) -> None:
        """Ensure a database has all required task properties.

        Fixes databases that were created under the broken 2025-09-03 API
        which silently ignored properties. Also renames the default 'Name'
        title property to 'Título' if needed.
        """
        logger.debug("Ensuring properties for space_id=%s", space_id[:8] + "...")
        try:
            logger.debug("API call: GET databases/%s", space_id)
            db = self.client.databases.retrieve(space_id)
            existing = db.get("properties", {})
            existing_names = set(existing.keys())

            updates = {}

            # Rename default "Name" title property to "Título"
            if "Name" in existing_names and "Título" not in existing_names:
                updates["Name"] = {"name": "Título", "title": {}}
                logger.info("Renaming 'Name' property to 'Título' for space_id=%s", space_id[:8] + "...")

            # Add all other missing non-title properties
            for prop_name, prop_schema in TASK_DB_PROPERTIES.items():
                if prop_name not in existing_names and prop_name != "Título":
                    updates[prop_name] = prop_schema

            if updates:
                logger.info("Updating %d missing properties for space_id=%s", len(updates), space_id[:8] + "...")
                logger.debug("API call: PATCH databases/%s", space_id)
                self.client.databases.update(
                    database_id=space_id, properties=updates
                )
                logger.info("Space properties updated successfully")
            else:
                logger.debug("All properties present for space_id=%s", space_id[:8] + "...")
        except Exception as e:
            logger.error("Failed to ensure space properties (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

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
        logger.debug("Getting tasks from space_id=%s with filters: status=%s, fecha_inicio=%s, fecha_fin=%s",
                    space_id[:8] + "...", status, fecha_inicio, fecha_fin)

        try:
            if fecha_inicio:
                fecha_inicio = _validate_date(fecha_inicio)
            if fecha_fin:
                fecha_fin = _validate_date(fecha_fin)

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

            logger.debug("API call: POST databases/%s/query", space_id)
            response = self.client.request(
                path=f"databases/{space_id}/query",
                method="POST",
                body=body,
            )
            tasks = [self._parse_task(page) for page in response["results"]]
            logger.info("Retrieved %d task(s) from space_id=%s", len(tasks), space_id[:8] + "...")
            return tasks
        except Exception as e:
            logger.error("Failed to get tasks (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

    def create_task(self, space_id: str, title: str, due_date: str | None = None,
                    priority: str = "Media", tags: list[str] | None = None,
                    notes: str | None = None, url: str | None = None) -> dict:
        """Create a task in a space."""
        logger.info("Creating task in space_id=%s with title='%s', due_date=%s, priority=%s",
                   space_id[:8] + "...", title, due_date, priority)

        try:
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

            logger.debug("API call: POST pages")
            page = self.client.pages.create(
                parent={"database_id": space_id},
                properties=properties,
            )
            task = self._parse_task(page)
            logger.info("Task created successfully with id=%s", task["id"][:8] + "...")
            return task
        except Exception as e:
            logger.error("Failed to create task (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

    def update_task(self, task_id: str, **updates) -> dict:
        """Update task properties. Accepts: title, due_date, status, priority, tags, notes, url."""
        logger.info("Updating task_id=%s with fields: %s", task_id[:8] + "...", list(updates.keys()))

        try:
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

            logger.debug("API call: PATCH pages/%s", task_id)
            page = self.client.pages.update(page_id=task_id, properties=properties)
            task = self._parse_task(page)
            logger.info("Task updated successfully")
            return task
        except Exception as e:
            logger.error("Failed to update task (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

    def delete_task(self, task_id: str) -> bool:
        """Archive (delete) a task."""
        logger.info("Deleting (archiving) task_id=%s", task_id[:8] + "...")
        try:
            logger.debug("API call: PATCH pages/%s", task_id)
            self.client.pages.update(page_id=task_id, archived=True)
            logger.info("Task deleted successfully")
            return True
        except Exception as e:
            logger.error("Failed to delete task (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

    def get_all_tasks(self, status: str | None = None,
                      fecha_inicio: str | None = None,
                      fecha_fin: str | None = None) -> list[dict]:
        """Get tasks from ALL spaces, with optional filters."""
        logger.info("Getting tasks from all spaces with filters: status=%s, fecha_inicio=%s, fecha_fin=%s",
                    status, fecha_inicio, fecha_fin)
        try:
            spaces = self.list_spaces()
            all_tasks = []
            for space in spaces:
                tasks = self.get_tasks(
                    space_id=space["id"], status=status,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                for task in tasks:
                    task["space_name"] = space["name"]
                all_tasks.extend(tasks)
            logger.info("get_all_tasks returned %d task(s) across %d space(s)",
                       len(all_tasks), len(spaces))
            return all_tasks
        except Exception as e:
            logger.error("Failed to get all tasks: %s", e, exc_info=True)
            raise

    def search_tasks(self, query: str) -> list[dict]:
        """Search tasks across all spaces."""
        logger.info("Searching tasks with query='%s'", query)
        try:
            logger.debug("API call: POST search")
            response = self.client.search(
                query=query,
                filter={"property": "object", "value": "page"},
            )
            tasks = []
            for page in response["results"]:
                if page.get("parent", {}).get("type") == "database_id":
                    try:
                        tasks.append(self._parse_task(page))
                    except (KeyError, IndexError) as e:
                        logger.warning("Failed to parse task page %s: %s", page.get("id", "unknown"), e)
                        continue
            logger.info("Search returned %d task(s)", len(tasks))
            return tasks
        except Exception as e:
            logger.error("Failed to search tasks (HTTP status=%s): %s", getattr(e, "status", None), e, exc_info=True)
            raise

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
