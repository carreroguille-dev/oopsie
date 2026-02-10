# Esquemas de Bases de Datos en Notion

## Página Raíz: Oopsie Hub

Página principal que contiene todos los espacios. Creada automáticamente por `scripts/setup.py`.

---

## Base de Datos: Espacios (Contexts)

Cada espacio representa un contexto o área de vida (ej: Casa, Universidad, Trabajo).

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| Nombre | `title` | Nombre del espacio |
| Icono | `emoji` | Emoji representativo |
| Fecha de creación | `created_time` | Fecha de creación automática |

### Ejemplo

```json
{
  "Nombre": { "title": [{ "text": { "content": "Universidad" } }] },
  "Icono": "🎓"
}
```

---

## Base de Datos: Tareas (por espacio)

Cada espacio tiene su propia base de datos de tareas.

| Propiedad | Tipo | Opciones | Descripción |
|-----------|------|----------|-------------|
| Título | `title` | — | Nombre de la tarea |
| Fecha de vencimiento | `date` | — | Fecha límite |
| Estado | `select` | Pendiente, En progreso, Completada | Estado actual |
| Prioridad | `select` | Baja, Media, Alta, Urgente | Nivel de prioridad |
| Etiquetas | `multi_select` | (dinámicas) | Tags para categorización |
| Enlaces | `url` | — | Recursos asociados |
| Notas | `rich_text` | — | Notas adicionales |

Las **subtareas** se almacenan como checkbox list dentro del contenido de la página de la tarea.

### Ejemplo

```json
{
  "Título": { "title": [{ "text": { "content": "Estudiar para examen de cálculo" } }] },
  "Fecha de vencimiento": { "date": { "start": "2026-03-15" } },
  "Estado": { "select": { "name": "Pendiente" } },
  "Prioridad": { "select": { "name": "Alta" } },
  "Etiquetas": { "multi_select": [{ "name": "examen" }, { "name": "matemáticas" }] },
  "Notas": { "rich_text": [{ "text": { "content": "Capítulos 5-8 del libro" } }] }
}
```

### Colores de Estado

| Estado | Color sugerido |
|--------|---------------|
| Pendiente | `default` (gris) |
| En progreso | `blue` |
| Completada | `green` |

### Colores de Prioridad

| Prioridad | Color sugerido |
|-----------|---------------|
| Baja | `gray` |
| Media | `yellow` |
| Alta | `orange` |
| Urgente | `red` |
