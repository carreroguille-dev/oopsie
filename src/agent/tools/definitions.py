"""LangChain tool definitions for the Oopsie agent.

Each @tool function IS both the schema (via type hints + docstring)
and the executor (calls NotionService directly).

NotionService is injected via `set_notion_service()` at startup.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from src.notion.client import NotionService

# Module-level service reference, set at startup
_notion: NotionService | None = None


def set_notion_service(notion: NotionService) -> None:
    """Inject the NotionService instance. Call this before using any tool."""
    global _notion
    _notion = notion


def _get_notion() -> NotionService:
    if _notion is None:
        raise RuntimeError("NotionService not initialized. Call set_notion_service() first.")
    return _notion


# --- Tools ---


@tool
def list_spaces() -> str:
    """Lista todos los espacios disponibles. LLAMA SIEMPRE A ESTA HERRAMIENTA PRIMERO si necesitas el space_id para otras operaciones. Devuelve JSON con una lista de objetos {id, name}."""
    spaces = _get_notion().list_spaces()
    return json.dumps({"spaces": spaces}, ensure_ascii=False)


@tool
def create_space(name: str, icon: str = "📁") -> str:
    """Crea un nuevo espacio para organizar tareas. Úsala cuando el usuario quiera un nuevo contexto (ej: "Crea un espacio para la universidad"). Devuelve el id y nombre del espacio creado.

    Args:
        name: Nombre del espacio. Ejemplo: "Universidad", "Casa", "Trabajo".
        icon: Un solo emoji representativo. Ejemplo: "🎓" para universidad, "🏠" para casa.
    """
    result = _get_notion().create_space(name=name, icon=icon)
    return json.dumps(result, ensure_ascii=False)


@tool
def get_tasks(space_id: str, status: str | None = None) -> str:
    """Obtiene las tareas de un espacio. Requiere space_id (obtenlo primero con list_spaces). Devuelve JSON con lista de tareas, cada una con: id, title, due_date, status, priority, tags, notes, url.

    Args:
        space_id: ID del espacio. Obténlo llamando a list_spaces primero.
        status: Filtro opcional. Valores exactos: "Pendiente", "En progreso", "Completada". Si se omite, devuelve todas.
    """
    tasks = _get_notion().get_tasks(space_id=space_id, status=status)
    return json.dumps({"tasks": tasks}, ensure_ascii=False)


@tool
def create_task(space_id: str, title: str, due_date: str | None = None,
                priority: str = "Media", tags: list[str] | None = None,
                notes: str | None = None, url: str | None = None) -> str:
    """Crea una nueva tarea dentro de un espacio. Requiere space_id (obtenlo con list_spaces) y un título. Devuelve la tarea creada con su id.

    Args:
        space_id: ID del espacio donde crear la tarea. Obténlo llamando a list_spaces.
        title: Título descriptivo de la tarea. Ejemplo: "Estudiar para examen de cálculo".
        due_date: Fecha de vencimiento en formato YYYY-MM-DD. Ejemplo: "2026-03-15". Convierte fechas relativas ("mañana") al formato antes de llamar.
        priority: Nivel de prioridad. Valores exactos: "Baja", "Media", "Alta", "Urgente". Por defecto "Media".
        tags: Lista de etiquetas. Ejemplo: ["examen", "matemáticas"].
        notes: Texto con notas adicionales. Ejemplo: "Capítulos 5-8 del libro".
        url: Enlace a un recurso relacionado. Ejemplo: "https://example.com/apuntes".
    """
    result = _get_notion().create_task(
        space_id=space_id, title=title, due_date=due_date,
        priority=priority, tags=tags, notes=notes, url=url,
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def update_task(task_id: str, title: str | None = None, due_date: str | None = None,
                status: str | None = None, priority: str | None = None,
                tags: list[str] | None = None, notes: str | None = None,
                url: str | None = None) -> str:
    """Actualiza campos de una tarea existente. Requiere task_id (obtenlo con get_tasks o search_tasks). Solo incluye los campos que cambien, omite el resto.

    Args:
        task_id: ID de la tarea a actualizar. Obténlo llamando a get_tasks o search_tasks.
        title: Nuevo título si cambia.
        due_date: Nueva fecha en formato YYYY-MM-DD si cambia.
        status: Nuevo estado. Valores exactos: "Pendiente", "En progreso", "Completada".
        priority: Nueva prioridad. Valores exactos: "Baja", "Media", "Alta", "Urgente".
        tags: Nueva lista completa de etiquetas (reemplaza las anteriores).
        notes: Nuevo texto de notas.
        url: Nuevo enlace.
    """
    updates = {k: v for k, v in {
        "title": title, "due_date": due_date, "status": status,
        "priority": priority, "tags": tags, "notes": notes, "url": url,
    }.items() if v is not None}
    result = _get_notion().update_task(task_id, **updates)
    return json.dumps(result, ensure_ascii=False)


@tool
def complete_task(task_id: str) -> str:
    """Marca una tarea como completada. Atajo para cambiar el estado a "Completada". Requiere task_id (obtenlo con get_tasks o search_tasks).

    Args:
        task_id: ID de la tarea a completar. Obténlo llamando a get_tasks o search_tasks.
    """
    result = _get_notion().update_task(task_id, status="Completada")
    return json.dumps(result, ensure_ascii=False)


@tool
def delete_task(task_id: str) -> str:
    """Elimina (archiva) una tarea permanentemente. IMPORTANTE: pide confirmación al usuario ANTES de llamar a esta herramienta. Requiere task_id.

    Args:
        task_id: ID de la tarea a eliminar. Obténlo llamando a get_tasks o search_tasks.
    """
    _get_notion().delete_task(task_id)
    return json.dumps({"deleted": True})


@tool
def search_tasks(query: str) -> str:
    """Busca tareas por texto en TODOS los espacios a la vez. Útil cuando el usuario no especifica un espacio concreto o quiere buscar globalmente. Devuelve lista de tareas con sus ids.

    Args:
        query: Texto a buscar en los títulos y contenido de las tareas. Ejemplo: "examen", "comprar".
    """
    tasks = _get_notion().search_tasks(query)
    return json.dumps({"tasks": tasks}, ensure_ascii=False)


# All tools as a list, ready to pass to create_react_agent
ALL_TOOLS = [
    list_spaces, create_space, get_tasks, create_task,
    update_task, complete_task, delete_task, search_tasks,
]
