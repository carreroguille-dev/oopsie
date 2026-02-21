from __future__ import annotations

import json
import logging
from typing import Callable

from langchain_core.tools import tool

from src.notion_cache.space_cache import SpaceCache
from src.notion.client import NotionService

logger = logging.getLogger(__name__)


def _safe(fn: Callable, *args, wrap_key: str | None = None, **kwargs) -> str:
    """Run a function and return JSON result, or JSON error on failure.

    Args:
        fn: Function to call.
        wrap_key: If provided, wraps the result as {wrap_key: result}.
    """
    try:
        result = fn(*args, **kwargs)
        logger.debug("Tool %s executed successfully", fn.__name__)
        payload = {wrap_key: result} if wrap_key else result
        return json.dumps(payload, ensure_ascii=False)
    except Exception as e:
        logger.error("Tool %s failed: %s", fn.__name__, e, exc_info=True)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def build_tools(notion: NotionService, cache: SpaceCache) -> list:
    """Build and return all agent tools with dependencies bound via closure."""

    @tool
    def list_spaces() -> str:
        """Lista todos los espacios. Devuelve {"spaces": [{"id", "name"}]}."""
        logger.info("Tool list_spaces called")
        return _safe(notion.list_spaces, wrap_key="spaces")

    @tool
    def create_space(name: str, icon: str = "📁") -> str:
        """Crea un nuevo espacio.

        Args:
            name: Nombre del espacio.
            icon: Emoji representativo (default "📁").
        """
        logger.info("Tool create_space called with name='%s', icon='%s'", name, icon)
        result = _safe(notion.create_space, name=name, icon=icon)
        if cache and '"error"' not in result:
            parsed = json.loads(result)
            cache.add(parsed["name"], parsed["id"])
        return result

    @tool
    def get_tasks(space_id: str, status: str | None = None,
                  fecha_inicio: str | None = None,
                  fecha_fin: str | None = None) -> str:
        """Obtiene tareas de un espacio con filtros opcionales.

        Args:
            space_id: UUID del espacio.
            status: Filtro por estado.
            fecha_inicio: Desde fecha YYYY-MM-DD (inclusive).
            fecha_fin: Hasta fecha YYYY-MM-DD (inclusive).
        """
        logger.info("Tool get_tasks called with space_id=%s, status=%s, fecha_inicio=%s, fecha_fin=%s",
                   space_id[:8] + "...", status, fecha_inicio, fecha_fin)
        return _safe(notion.get_tasks,
                     space_id=space_id, status=status,
                     fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                     wrap_key="tasks")

    @tool
    def create_task(space_id: str, title: str, due_date: str | None = None,
                    priority: str = "Media", tags: list[str] | None = None,
                    notes: str | None = None, url: str | None = None) -> str:
        """Crea una tarea en un espacio.

        Args:
            space_id: UUID del espacio.
            title: Título de la tarea.
            due_date: Fecha YYYY-MM-DD.
            priority: "Baja"/"Media"/"Alta"/"Urgente" (default "Media").
            tags: Lista de etiquetas.
            notes: Notas adicionales.
            url: Enlace relacionado.
        """
        logger.info("Tool create_task called with space_id=%s, title='%s', due_date=%s, priority=%s",
                   space_id[:8] + "...", title, due_date, priority)
        return _safe(notion.create_task,
                     space_id=space_id, title=title, due_date=due_date,
                     priority=priority, tags=tags, notes=notes, url=url)

    @tool
    def update_task(task_id: str, title: str | None = None, due_date: str | None = None,
                    status: str | None = None, priority: str | None = None,
                    tags: list[str] | None = None, notes: str | None = None,
                    url: str | None = None) -> str:
        """Actualiza campos de una tarea. Solo incluye campos que cambien.

        Args:
            task_id: UUID de la tarea.
            title: Nuevo título.
            due_date: Nueva fecha YYYY-MM-DD.
            status: Nuevo estado.
            priority: Nueva prioridad.
            tags: Nueva lista de etiquetas (reemplaza anteriores).
            notes: Nuevas notas.
            url: Nuevo enlace.
        """
        updates = {k: v for k, v in {
            "title": title, "due_date": due_date, "status": status,
            "priority": priority, "tags": tags, "notes": notes, "url": url,
        }.items() if v is not None}
        logger.info("Tool update_task called with task_id=%s, updates=%s", task_id[:8] + "...", list(updates.keys()))
        return _safe(notion.update_task, task_id, **updates)

    @tool
    def complete_task(task_id: str) -> str:
        """Marca una tarea como completada.

        Args:
            task_id: UUID de la tarea.
        """
        logger.info("Tool complete_task called with task_id=%s", task_id[:8] + "...")
        return _safe(notion.update_task, task_id, status="Completada")

    @tool
    def delete_task(task_id: str) -> str:
        """Elimina (archiva) una tarea. Pide confirmación al usuario ANTES de llamar.

        Args:
            task_id: UUID de la tarea.
        """
        logger.warning("Tool delete_task called with task_id=%s", task_id[:8] + "...")
        return _safe(notion.delete_task, task_id)

    @tool
    def get_all_tasks(status: str | None = None,
                      fecha_inicio: str | None = None,
                      fecha_fin: str | None = None) -> str:
        """Obtiene tareas de TODOS los espacios a la vez. Usa esta herramienta cuando el usuario pida tareas sin especificar un espacio concreto.

        Args:
            status: Filtro por estado ("Pendiente", "En progreso", "Completada").
            fecha_inicio: Desde fecha YYYY-MM-DD (inclusive).
            fecha_fin: Hasta fecha YYYY-MM-DD (inclusive).
        """
        logger.info("Tool get_all_tasks called with status=%s, fecha_inicio=%s, fecha_fin=%s",
                   status, fecha_inicio, fecha_fin)
        return _safe(notion.get_all_tasks,
                     status=status, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                     wrap_key="tasks")

    @tool
    def search_tasks(query: str) -> str:
        """Busca tareas por texto en todos los espacios.

        Args:
            query: Texto a buscar.
        """
        logger.info("Tool search_tasks called with query='%s'", query)
        return _safe(notion.search_tasks, query, wrap_key="tasks")

    return [
        list_spaces, create_space, get_tasks, get_all_tasks, create_task,
        update_task, complete_task, delete_task, search_tasks,
    ]
