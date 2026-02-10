# 🎯 ROADMAP: Oopsie - Asistente Personal de Tareas con Notion + IA

> Asistente inteligente para gestión de tareas mediante lenguaje natural, con entrada por voz, integración con Notion vía MCP, y personalidad informal.

---

## 📋 Resumen del Proyecto

| Aspecto | Decisión |
|---------|----------|
| **Nombre** | Oopsie |
| **Modelo LLM** | Kimi K2.5 (vía OpenRouter) |
| **Proveedor LLM** | OpenRouter (API OpenAI-compatible) |
| **Speech-to-Text** | Faster-Whisper - Open source, local |
| **Backend** | Notion (vía MCP) |
| **Interfaz** | Gradio (móvil-first, modo oscuro) |
| **Observabilidad** | Langfuse (trazado y monitoreo LLM) |
| **Entorno** | Conda + pip |
| **Licencia** | MIT |

---

## Fase 1: Preparación y Configuración del Entorno

### 1.1 Configuración de Notion

- [ ] Crear integración de Notion en [developers.notion.com](https://developers.notion.com)
- [ ] Obtener API key (Internal Integration Token)
- [ ] Documentar proceso de creación de integración para el README
- [ ] Definir permisos mínimos necesarios para la integración

### 1.2 Diseño de la Estructura de Datos

- [ ] Definir esquema de la página raíz "Oopsie Hub"
- [ ] Diseñar plantilla de base de datos para espacios/contextos:
  - Título (title)
  - Icono (emoji)
  - Fecha de creación (created_time)
- [ ] Diseñar plantilla de base de datos para tareas:
  - Título (title)
  - Fecha de vencimiento (date)
  - Estado (select): Pendiente, En progreso, Completada
  - Prioridad (select): Baja, Media, Alta, Urgente
  - Etiquetas (multi-select)
  - Enlaces/Recursos (url)
  - Subtareas (checkbox list dentro del contenido de la página)
  - Notas (rich text)
- [ ] Documentar esquema en formato JSON/YAML para referencia

### 1.3 Script de Setup Automático

- [ ] Crear script `setup.py` que:
  - Verifique conexión con API de Notion
  - Cree página raíz "Oopsie Hub" vacía
  - Guarde el ID de la página raíz en configuración local
  - Muestre instrucciones post-setup
- [ ] Manejar errores comunes (API key inválida, permisos insuficientes)
- [ ] Implementar flag `--force` para recrear estructura si ya existe

### 1.4 Configuración del Entorno de Desarrollo

- [ ] Crear repositorio en GitHub: `oopsie`
- [ ] Crear estructura de carpetas:
```
oopsie/
├── src/
│   ├── agent/          # Lógica del agente IA (tools/, prompts/)

│   ├── mcp/            # Cliente MCP y operaciones Notion
│   ├── voice/          # Speech-to-text
│   ├── interface/      # Aplicación Gradio
│   └── utils/          # Utilidades comunes
├── scripts/
│   ├── setup.py        # Script de inicialización
│   └── seed_test_data.py  # Generador de datos de prueba
├── config/
│   └── config.example.yaml
├── docs/
│   └── SCHEMA.md       # Esquemas de bases de datos Notion
├── environment.yml
├── requirements.txt
├── .gitignore
├── .env.example
├── LICENSE
└── README.md
```
- [ ] Crear `environment.yml` con dependencias Conda
- [ ] Crear `requirements.txt` con dependencias pip
- [ ] Crear `.env.example` con variables necesarias:
  - `NOTION_API_KEY`
  - `NOTION_ROOT_PAGE_ID`
  - `OPENROUTER_API_KEY`
  - `LANGFUSE_SECRET_KEY`
  - `LANGFUSE_PUBLIC_KEY`
  - `LANGFUSE_HOST`
- [ ] Crear `.gitignore` completo
- [ ] Añadir archivo `LICENSE` (MIT)

---

## Fase 2: Investigación e Implementación del MCP de Notion

### 2.1 Investigación del MCP

- [ ] Estudiar documentación oficial del MCP de Notion
- [ ] Identificar operaciones soportadas:
  - Lectura de páginas
  - Lectura de bases de datos
  - Creación de páginas
  - Creación de entradas en bases de datos
  - Actualización de propiedades
  - Eliminación de páginas/entradas
  - Búsqueda y filtrado
- [ ] Documentar limitaciones conocidas
- [ ] Identificar workarounds para limitaciones
- [ ] Crear documento `docs/MCP_NOTION_REFERENCE.md` con hallazgos

### 2.2 Instalación y Configuración del MCP

- [ ] Instalar servidor MCP de Notion
- [ ] Configurar conexión con API de Notion
- [ ] Crear script de arranque del servidor MCP
- [ ] Documentar proceso de instalación

### 2.3 Desarrollo del Cliente MCP

- [ ] Implementar clase `NotionMCPClient` en `src/mcp/client.py`
- [ ] Implementar métodos base:
  - `connect()` / `disconnect()`
  - `health_check()`
- [ ] Implementar manejo de errores y reconexión
- [ ] Configurar logging de operaciones

### 2.4 Implementación de Operaciones CRUD

- [ ] Implementar `get_root_page()` - Obtener página raíz
- [ ] Implementar `list_spaces()` - Listar espacios/contextos
- [ ] Implementar `create_space(name, icon)` - Crear nuevo espacio con su base de datos
- [ ] Implementar `get_tasks(space_id, filters)` - Obtener tareas con filtros
- [ ] Implementar `create_task(space_id, task_data)` - Crear tarea
- [ ] Implementar `update_task(task_id, updates)` - Actualizar tarea
- [ ] Implementar `delete_task(task_id)` - Eliminar tarea
- [ ] Implementar `search_tasks(query)` - Buscar tareas por texto

### 2.5 Pruebas de Operaciones

- [ ] Probar cada operación manualmente
- [ ] Verificar integridad de datos en Notion
- [ ] Documentar casos edge y comportamientos inesperados

### 2.6 Arquitectura para Despliegue Futuro

- [ ] Diseñar abstracción que permita MCP local o remoto
- [ ] Implementar configuración por variable de entorno:
  - `MCP_MODE=local` (por defecto)
  - `MCP_MODE=remote` + `MCP_SERVER_URL`
- [ ] Documentar arquitectura en `docs/ARCHITECTURE.md`

---

## Fase 3: Desarrollo del Agente de IA

### 3.1 Configuración del Modelo

- [ ] Implementar cliente para Kimi K2.5 vía OpenRouter en `src/agent/llm_client.py`
- [ ] Configurar endpoint OpenRouter y autenticación (formato OpenAI-compatible)
- [ ] Integrar Langfuse para trazado y observabilidad de llamadas LLM
- [ ] Implementar manejo de rate limits y reintentos
- [ ] Crear configuración de modelo (temperatura, max_tokens, etc.)

### 3.2 Diseño del System Prompt

- [ ] Crear prompt base con personalidad de Oopsie:
  - Tono informal y amigable
  - Siempre responde en español
  - Proactivo: sugiere y recuerda tareas próximas
  - Usa humor ligero acorde al nombre "Oopsie"
- [ ] Incluir instrucciones sobre herramientas disponibles
- [ ] Definir formato de respuestas esperado
- [ ] Incluir ejemplos de interacciones
- [ ] Guardar en `src/agent/prompts/system_prompt.txt`

### 3.3 Implementación del Esquema de Herramientas

- [ ] Definir herramientas (tools/functions) para el agente:
  - `list_spaces` - Listar espacios disponibles
  - `create_space` - Crear nuevo espacio
  - `get_tasks` - Obtener tareas (con filtros)
  - `create_task` - Crear nueva tarea
  - `update_task` - Actualizar tarea existente
  - `complete_task` - Marcar tarea como completada
  - `delete_task` - Eliminar tarea (requiere confirmación)
  - `search_tasks` - Buscar tareas
  - `get_upcoming_tasks` - Tareas próximas a vencer
- [ ] Implementar cada herramienta en `src/agent/tools/`
- [ ] Conectar herramientas con cliente MCP

### 3.4 Módulo de Resolución Temporal

- [ ] Instalar y configurar `dateparser` con locale español
- [ ] Implementar `src/utils/time_resolver.py`:
  - Parsear "mañana", "el martes que viene", "dentro de 3 días"
  - Parsear "final de mes", "próxima semana"
  - Manejar ambigüedades (preguntar si es necesario)
- [ ] Configurar zona horaria por defecto (configurable)
- [ ] Crear batería de expresiones de prueba

### 3.5 Implementación del Núcleo del Agente

- [ ] Crear clase `OopsieAgent` en `src/agent/core.py`
- [ ] Implementar bucle de conversación con tool calling
- [ ] Implementar memoria de sesión (historial de mensajes)
- [ ] Implementar lógica de confirmación para eliminaciones:
  - Detectar intención de eliminar
  - Solicitar confirmación explícita
  - Proceder solo con confirmación
- [ ] Implementar comportamiento proactivo:
  - Al inicio de sesión: revisar tareas próximas a vencer
  - Sugerir acciones basadas en contexto

### 3.6 Manejo de Contexto y Ambigüedades

- [ ] Implementar caché de estructura de Notion (espacios y sus IDs)
- [ ] Actualizar caché cuando se crean/eliminan espacios
- [ ] Implementar resolución de ambigüedades:
  - Si hay múltiples espacios similares, preguntar cuál
  - Si falta información para crear tarea, preguntar
- [ ] Manejar referencias implícitas ("añade otra", "en el mismo sitio")

---

## Fase 4: Desarrollo de la Interfaz Gradio

### 4.1 Configuración Base de Gradio

- [ ] Crear aplicación Gradio en `src/interface/app.py`
- [ ] Configurar tema oscuro por defecto
- [ ] Configurar para acceso en red local (`server_name="0.0.0.0"`)
- [ ] Optimizar layout para móvil (móvil-first)

### 4.2 Componentes de Entrada

- [ ] Implementar campo de texto para consultas
- [ ] Implementar botón de envío
- [ ] Implementar grabación de audio con `gr.Audio`
- [ ] Añadir indicador visual de "grabando"

### 4.3 Integración Speech-to-Text

- [ ] Instalar Faster-Whisper (versión optimizada de Whisper)
- [ ] Crear módulo `src/voice/transcriber.py`
- [ ] Configurar modelo (base, small, medium según recursos)
- [ ] Implementar transcripción de audio a texto
- [ ] Optimizar para latencia (modelo small recomendado)
- [ ] Manejar errores de transcripción

### 4.4 Componentes de Salida

- [ ] Implementar área de chat con historial
- [ ] Crear componente de visualización de tareas (tarjetas):
  - Título
  - Fecha de vencimiento (con formato relativo: "en 2 días")
  - Estado (con color)
  - Prioridad (con icono/color)
  - Espacio al que pertenece
- [ ] Implementar tabla alternativa para listas largas
- [ ] Añadir indicadores de estado:
  - "Procesando..." durante llamadas al agente
  - "Error" con mensaje descriptivo
  - "Listo" tras completar acción

### 4.5 Flujo de Interacción

- [ ] Conectar entrada de texto con agente
- [ ] Conectar entrada de voz → transcripción → agente
- [ ] Mostrar texto transcrito antes de enviar (para verificación)
- [ ] Implementar historial de conversación visible
- [ ] Añadir botón "Nueva conversación" para resetear sesión

### 4.6 Mejoras de UX

- [ ] Añadir ejemplos de consultas sugeridas como placeholders
- [ ] Implementar atajos:
  - Enter para enviar texto
  - Botón dedicado para voz
- [ ] Mostrar notificaciones para acciones completadas
- [ ] Manejar errores de forma amigable (sin tecnicismos)
- [ ] Añadir mensaje de bienvenida proactivo al iniciar

---

## Fase 5: Entorno de Pruebas

### 5.1 Script de Datos de Prueba

- [ ] Crear `scripts/seed_test_data.py` que genere:
  - 3-4 espacios de ejemplo (Casa, Universidad, Trabajo, Personal)
  - 10-15 tareas distribuidas entre espacios
  - Tareas con diferentes estados y prioridades
  - Tareas con fechas pasadas, hoy, próximas, y futuras
- [ ] Implementar flag `--clean` para eliminar datos de prueba
- [ ] Documentar uso del script

### 5.2 Verificación Manual

- [ ] Crear checklist de funcionalidades a probar:
  - [ ] Crear espacio
  - [ ] Listar espacios
  - [ ] Crear tarea con fecha relativa
  - [ ] Listar tareas pendientes
  - [ ] Filtrar tareas por espacio
  - [ ] Completar tarea
  - [ ] Eliminar tarea (verificar confirmación)
  - [ ] Búsqueda de tareas
  - [ ] Entrada por voz
  - [ ] Comportamiento proactivo
- [ ] Probar en móvil (interfaz responsive)
- [ ] Probar en diferentes navegadores

---

## Fase 6: Documentación y Despliegue

### 6.1 README Principal

- [ ] Escribir README.md completo en español:
  - Descripción del proyecto
  - Capturas de pantalla / GIFs de uso
  - Requisitos previos
  - Guía de instalación paso a paso:
    1. Clonar repositorio
    2. Crear entorno Conda
    3. Configurar integración Notion
    4. Configurar API keys
    5. Ejecutar setup
    6. Lanzar aplicación
  - Ejemplos de uso (consultas de ejemplo)
  - Configuración avanzada
  - Solución de problemas comunes
  - Contribuir al proyecto
  - Licencia

### 6.2 Scripts de Arranque

- [ ] Crear `run.sh` / `run.bat` para arranque unificado:
  - Verificar entorno activo
  - Iniciar servidor MCP
  - Lanzar aplicación Gradio
- [ ] Documentar puertos utilizados
- [ ] Implementar modo desarrollo vs producción

### 6.3 Preparación para Publicación

- [ ] Revisar que no haya secrets en el código
- [ ] Verificar `.gitignore` completo
- [ ] Añadir badges al README (licencia, Python version)
- [ ] Crear release inicial v0.1.0

---

## Fase 7: Extensiones Futuras (Backlog)

> Ordenadas por prioridad según preferencias del usuario.

### 7.1 Integración con Google Calendar (Prioridad: Alta)

- [ ] Configurar OAuth2 para Google Calendar API
- [ ] Implementar sincronización bidireccional:
  - Tareas con fecha → Eventos en calendario
  - Eventos del calendario → Contexto para el agente
- [ ] Añadir herramienta `check_calendar` para el agente
- [ ] Resolver conflictos de fechas

### 7.2 Notificaciones - Telegram (Prioridad: Alta)

- [ ] Crear bot de Telegram para Oopsie
- [ ] Implementar notificaciones:
  - Recordatorio de tareas próximas a vencer
  - Resumen diario matutino
  - Confirmación de acciones importantes
- [ ] Permitir responder desde Telegram (entrada alternativa)

### 7.3 Notificaciones - Email (Prioridad: Alta)

- [ ] Configurar envío de emails (SMTP o servicio)
- [ ] Implementar plantillas de email
- [ ] Añadir preferencias de frecuencia de notificaciones

### 7.4 Estadísticas de Productividad (Prioridad: Media)

- [ ] Rastrear métricas:
  - Tareas completadas por día/semana/mes
  - Tiempo promedio de completado
  - Distribución por espacio
  - Tasa de tareas vencidas
- [ ] Crear dashboard de estadísticas en Gradio
- [ ] Implementar consultas al agente:
  - "¿Cuántas tareas completé esta semana?"
  - "¿En qué área tengo más pendientes?"

### 7.5 Tareas Recurrentes (Prioridad: Media)

- [ ] Extender esquema de tareas para recurrencia:
  - Diaria, semanal, mensual, personalizada
- [ ] Implementar lógica de regeneración automática
- [ ] Añadir comandos: "Recuérdame esto cada lunes"

### 7.6 Importar Tareas desde Otras Fuentes (Prioridad: Baja)

- [ ] Importar desde CSV/JSON
- [ ] Importar desde Todoist
- [ ] Importar desde Google Tasks
- [ ] Importar desde Apple Reminders

---

## 📊 Métricas de Progreso

| Fase | Estado | Progreso |
|------|--------|----------|
| Fase 1: Preparación | ⬜ Pendiente | 0% |
| Fase 2: MCP Notion | ⬜ Pendiente | 0% |
| Fase 3: Agente IA | ⬜ Pendiente | 0% |
| Fase 4: Interfaz | ⬜ Pendiente | 0% |
| Fase 5: Pruebas | ⬜ Pendiente | 0% |
| Fase 6: Documentación | ⬜ Pendiente | 0% |
| Fase 7: Extensiones | ⬜ Backlog | - |

---

## 🔧 Stack Tecnológico Final

| Componente | Tecnología |
|------------|------------|
| Lenguaje | Python 3.11 |
| Entorno | Conda + pip |
| LLM | Kimi K2.5 (vía OpenRouter, API OpenAI-compatible) |
| Proveedor LLM | OpenRouter |
| STT | Faster-Whisper (local) |
| Backend | Notion API vía MCP |
| Interfaz | Gradio |
| Observabilidad | Langfuse (trazado LLM) |
| Notificaciones (futuro) | Telegram Bot API, SMTP |
| Calendario (futuro) | Google Calendar API |

---

*Última actualización: Febrero 2026*
*Licencia: MIT*