from __future__ import annotations

import json

from langchain_core.tools import tool

from src.notion.client import NotionService

_notion: NotionService | None = None


def set_notion_service(notion: NotionService) -> None:
    """Inject the NotionService instance. Call this before using any tool."""
    global _notion
    _notion = notion


def _get_notion() -> NotionService:
    if _notion is None:
        raise RuntimeError("NotionService not initialized. Call set_notion_service() first.")
    return _notion


def _safe(fn, *args, **kwargs) -> str:
    """Run a function and return JSON result, or JSON error on failure."""
    try:
        result = fn(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        print(f"[TOOL ERROR] {fn.__name__}({args}, {kwargs}): {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# --- Tools ---

@tool
def list_spaces() -> str:
    """Lista todos los espacios disponibles. LLAMA SIEMPRE A ESTA HERRAMIENTA PRIMERO cuando necesites un space_id. NO inventes IDs. Devuelve JSON: {"spaces": [{"id": "uuid", "name": "Nombre"}]}. Si la lista está vacía, el usuario debe crear un espacio primero con create_space."""
    try:
        spaces = _get_notion().list_spaces()
        return json.dumps({"spaces": spaces}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def create_space(name: str, icon: str = "📁") -> str:
    """Crea un nuevo espacio para organizar tareas. Úsala cuando el usuario quiera un nuevo contexto. Devuelve JSON con el id y nombre del espacio creado.

    Args:
        name: Nombre del espacio. Ejemplo: "Universidad", "Casa", "Trabajo".
        icon: Un solo emoji representativo. Ejemplo: "🎓" para universidad, "🏠" para casa.
    """
    return _safe(_get_notion().create_space, name=name, icon=icon)


@tool
def get_tasks(space_id: str, status: str | None = None,
              fecha_inicio: str | None = None,
              fecha_fin: str | None = None) -> str:
    """Obtiene las tareas de un espacio, con filtros opcionales por estado y/o rango de fechas. IMPORTANTE: el space_id debe ser un UUID real obtenido de list_spaces. NO inventes IDs. Devuelve JSON con lista de tareas.

    Cuando el usuario pide "tareas de esta semana", calcula el lunes y domingo de la semana actual y pásalos como fecha_inicio y fecha_fin.

    Args:
        space_id: UUID del espacio. DEBE obtenerse llamando a list_spaces primero.
        status: Filtro opcional. Valores EXACTOS: "Pendiente", "En progreso", "Completada".
        fecha_inicio: Fecha inicio del rango en formato YYYY-MM-DD. Solo devuelve tareas con fecha de vencimiento >= esta fecha.
        fecha_fin: Fecha fin del rango en formato YYYY-MM-DD. Solo devuelve tareas con fecha de vencimiento <= esta fecha.
    """
    try:
        tasks = _get_notion().get_tasks(
            space_id=space_id, status=status,
            fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
        )
        return json.dumps({"tasks": tasks}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def create_task(space_id: str, title: str, due_date: str | None = None,
                priority: str = "Media", tags: list[str] | None = None,
                notes: str | None = None, url: str | None = None) -> str:
    """Crea una nueva tarea dentro de un espacio. IMPORTANTE: el space_id debe ser un UUID real obtenido de list_spaces. NO inventes IDs. Si no hay espacios, dile al usuario que cree uno primero.

    Args:
        space_id: UUID del espacio. DEBE obtenerse llamando a list_spaces primero.
        title: Título descriptivo de la tarea.
        due_date: Fecha en formato YYYY-MM-DD. Convierte "mañana", "el martes" etc. al formato antes de llamar.
        priority: Valores EXACTOS: "Baja", "Media", "Alta", "Urgente". Por defecto "Media".
        tags: Lista de etiquetas. Ejemplo: ["examen", "matemáticas"].
        notes: Notas adicionales en texto libre.
        url: Enlace a un recurso.
    """
    return _safe(_get_notion().create_task,
                 space_id=space_id, title=title, due_date=due_date,
                 priority=priority, tags=tags, notes=notes, url=url)


@tool
def update_task(task_id: str, title: str | None = None, due_date: str | None = None,
                status: str | None = None, priority: str | None = None,
                tags: list[str] | None = None, notes: str | None = None,
                url: str | None = None) -> str:
    """Actualiza campos de una tarea existente. Solo incluye los campos que cambien. IMPORTANTE: el task_id debe ser un UUID real obtenido de get_tasks o search_tasks.

    Args:
        task_id: UUID de la tarea. DEBE obtenerse de get_tasks o search_tasks.
        title: Nuevo título si cambia.
        due_date: Nueva fecha en formato YYYY-MM-DD si cambia.
        status: Valores EXACTOS: "Pendiente", "En progreso", "Completada".
        priority: Valores EXACTOS: "Baja", "Media", "Alta", "Urgente".
        tags: Nueva lista completa de etiquetas (reemplaza las anteriores).
        notes: Nuevo texto de notas.
        url: Nuevo enlace.
    """
    updates = {k: v for k, v in {
        "title": title, "due_date": due_date, "status": status,
        "priority": priority, "tags": tags, "notes": notes, "url": url,
    }.items() if v is not None}
    return _safe(_get_notion().update_task, task_id, **updates)


@tool
def complete_task(task_id: str) -> str:
    """Marca una tarea como completada. IMPORTANTE: el task_id debe ser un UUID real obtenido de get_tasks o search_tasks.

    Args:
        task_id: UUID de la tarea. DEBE obtenerse de get_tasks o search_tasks.
    """
    return _safe(_get_notion().update_task, task_id, status="Completada")


@tool
def delete_task(task_id: str) -> str:
    """Elimina (archiva) una tarea permanentemente. IMPORTANTE: pide confirmación al usuario ANTES de llamar. El task_id debe ser un UUID real.

    Args:
        task_id: UUID de la tarea. DEBE obtenerse de get_tasks o search_tasks.
    """
    return _safe(_get_notion().delete_task, task_id)


@tool
def search_tasks(query: str) -> str:
    """Busca tareas por texto en TODOS los espacios a la vez. Útil cuando el usuario no especifica un espacio o quiere buscar globalmente. Devuelve lista de tareas con sus UUIDs.

    Args:
        query: Texto a buscar. Ejemplo: "examen", "comprar".
    """
    try:
        tasks = _get_notion().search_tasks(query)
        return json.dumps({"tasks": tasks}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# All tools as a list, ready to pass to create_react_agent
ALL_TOOLS = [
    list_spaces, create_space, get_tasks, create_task,
    update_task, complete_task, delete_task, search_tasks,
]
