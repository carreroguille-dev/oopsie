# Oopsie — Architecture & Developer Guide

> Teaching notes for junior developers: what each part does, why it's used, and how everything connects.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [How the App Works (Big Picture)](#how-the-app-works-big-picture)
3. [Libraries Used](#libraries-used)
4. [Project Structure](#project-structure)
5. [Module-by-Module Breakdown](#module-by-module-breakdown)
6. [Data Flow: What Happens When You Send a Message](#data-flow-what-happens-when-you-send-a-message)
7. [Key Concepts](#key-concepts)

---

## Project Overview

Oopsie is a personal task assistant. You talk to it in natural Spanish, and it manages your tasks in Notion. It can:

- Create "spaces" (like folders: University, Home, Work)
- Add, edit, complete, delete and search tasks inside those spaces
- Understand voice input
- Understand dates like "mañana" or "el martes que viene"

The core idea: an **LLM (large language model)** receives the user's message, decides which **tools** to call (create task, list spaces, etc.), executes them against the **Notion API**, and returns a friendly response.

---

## How the App Works (Big Picture)

```
User (text or voice)
        │
        ▼
┌──────────────────┐
│  Gradio Interface │  ← Thin UI layer, easily replaceable
│  (app.py)         │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  OopsieAgent      │  ← Wraps the LangGraph ReAct agent
│  (core.py)        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  LangGraph        │  ← ReAct loop: LLM ↔ Tools automatically
│  create_react_    │
│  agent            │
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│ChatOpen│ │ @tool funcs  │  ← Each tool calls NotionService directly
│   AI   │ │(definitions  │
│        │ │      .py)    │
└────────┘ └──────┬───────┘
                  │
                  ▼
          ┌──────────────┐
          │ NotionService │  ← Talks to Notion API
          │ (client.py)   │
          └──────────────┘
```

---

## Libraries Used

### Core Dependencies

| Library | What it does | Why we use it |
|---------|-------------|---------------|
| **langchain** | Framework for building LLM applications | Provides the `@tool` decorator, message types, and integration layer. It standardizes how we define tools and interact with LLMs, regardless of provider. |
| **langgraph** | State machine framework for LLM agents | Provides `create_react_agent` — a prebuilt ReAct loop that handles the LLM ↔ tool calling cycle automatically. Also provides `MemorySaver` for conversation memory. This is what makes it easy to add more specialized agents later. |
| **langchain-openai** | LangChain integration for OpenAI-compatible APIs | Provides `ChatOpenAI` class that connects to OpenRouter (or any OpenAI-compatible endpoint). Handles authentication, tool binding, and response parsing. |
| **openai** | Python SDK for OpenAI-compatible APIs | Underlying HTTP client used by `langchain-openai`. We don't call it directly. |
| **notion-client** | Official Python SDK for the Notion API | Lets us create pages, query databases, update properties, and search in Notion. It wraps the REST API so we don't have to build HTTP requests manually. |
| **gradio** | Web UI framework for Python | Creates a web interface (chat + audio input) with a few lines of code. Good for prototyping. The interface is intentionally thin so it can be replaced with Angular+Ionic or another framework later. |
| **faster-whisper** | Local speech-to-text engine | An optimized version of OpenAI's Whisper model. Runs locally (no API calls), supports Spanish, and is fast enough for real-time use. The "small" model balances accuracy and speed. |
| **dateparser** | Natural language date parsing | Understands expressions like "mañana", "el martes que viene", "dentro de 3 días" in Spanish and converts them to actual dates. Saves us from building a date parser from scratch. |

### Utility Dependencies

| Library | What it does | Why we use it |
|---------|-------------|---------------|
| **python-dotenv** | Loads `.env` files into environment variables | Keeps secrets (API keys) out of source code. The `.env` file is gitignored, so keys never get committed. |
| **pyyaml** | Parses YAML files | Our config file (`config.yaml`) uses YAML format — it's more readable than JSON for configuration. |
| **langfuse** | LLM observability and tracing | Will let us track LLM calls, costs, and performance in a dashboard. Can be wired into LangChain via a callback handler. |

---

## Project Structure

```
oopsie/
├── src/
│   ├── main.py                     # Entry point — wires everything together
│   ├── agent/
│   │   ├── core.py                 # OopsieAgent — wraps LangGraph ReAct agent
│   │   ├── prompts/
│   │   │   └── system_prompt.txt   # Oopsie's personality and rules
│   │   └── tools/
│   │       └── definitions.py      # @tool functions (schema + execution in one)
│   ├── notion/
│   │   └── client.py               # NotionService — all Notion operations
│   ├── voice/
│   │   └── transcriber.py          # Speech-to-text
│   ├── interface/
│   │   └── app.py                  # Gradio UI
│   └── utils/
│       ├── config.py               # Loads config + env vars
│       └── time_resolver.py        # "mañana" → "2026-02-12"
├── scripts/
│   └── setup.py                    # Creates Oopsie Hub page in Notion
├── config/
│   └── config.example.yaml         # Default configuration
├── docs/
│   ├── SCHEMA.md                   # Notion database schemas
│   └── ARCHITECTURE.md             # This file
├── requirements.txt
├── environment.yml
├── .env.example
└── .gitignore
```

---

## Module-by-Module Breakdown

### `src/main.py` — Entry Point

**What it does**: Initializes every component and starts the app.

**How it works**:
1. Loads config (YAML file + environment variables)
2. Creates a `NotionService` (connects to Notion)
3. Injects NotionService into the tools module via `set_notion_service()`
4. Creates the `OopsieAgent` (builds LangGraph agent internally)
5. Optionally creates a `Transcriber` (voice input — skipped if it fails to load)
6. Creates and launches the Gradio app

**Why it's separate**: Keeps initialization logic in one place. Each component is created independently, making it easy to test or replace any piece.

---

### `src/utils/config.py` — Configuration

**What it does**: Loads settings from two sources and merges them.

**Source 1 — YAML file** (`config/config.yaml`):
```yaml
llm:
  model: "moonshotai/kimi-k2.5"
  base_url: "https://openrouter.ai/api/v1"
  temperature: 0.7        # How "creative" the LLM is (0=deterministic, 1=creative)
  max_tokens: 2048         # Max response length
```

**Source 2 — Environment variables** (`.env`):
```
NOTION_API_KEY=ntn_xxxxx
OPENROUTER_API_KEY=sk-or-xxxxx
```

**Why two sources**: Configuration (model name, port, etc.) is safe to commit to git. Secrets (API keys) must never be committed — they live in `.env` which is gitignored.

**Key function**:
- `load_config()` → Returns a single dict with everything merged.

---

### `src/utils/time_resolver.py` — Date Parsing

**What it does**: Converts Spanish natural language dates to ISO format.

```python
resolve_date("mañana")          # → "2026-02-12"
resolve_date("el martes")       # → "2026-02-17"
resolve_date("dentro de 3 días") # → "2026-02-14"
```

**How it works**: The `dateparser` library does the heavy lifting. We configure it with:
- `languages=["es"]` — parse Spanish
- `PREFER_DATES_FROM: "future"` — "martes" means *next* Tuesday, not last
- `TIMEZONE` — ensures dates are correct for your timezone

**Key function**:
- `resolve_date(text, timezone)` → Returns `"YYYY-MM-DD"` string or `None` if it can't parse.

---

### `src/notion/client.py` — Notion Service

**What it does**: All communication with Notion. This is the only file that talks to the Notion API.

**Key concept — Spaces and Tasks**:
- A **space** = a Notion database (e.g., "University", "Home")
- A **task** = a page (row) inside that database
- All spaces live under a single root page called "Oopsie Hub"

**Class `NotionService`**:

| Method | What it does |
|--------|-------------|
| `list_spaces()` | Lists all databases under the root page |
| `create_space(name, icon)` | Creates a new database with the task schema (columns for title, date, status, priority, tags, notes, url) |
| `get_tasks(space_id, status)` | Queries a database for tasks, optionally filtered by status |
| `create_task(space_id, title, ...)` | Creates a new page in the database |
| `update_task(task_id, **updates)` | Updates specific properties of a task |
| `delete_task(task_id)` | Archives a task (Notion doesn't truly delete — it archives) |
| `search_tasks(query)` | Full-text search across all spaces |
| `_parse_task(page)` | Internal helper: converts Notion's verbose page object into a clean dict |

**Why `_parse_task` exists**: Notion returns deeply nested JSON. A task title looks like:
```json
{"properties": {"Título": {"title": [{"text": {"content": "Buy milk"}}]}}}
```
The parser flattens this to:
```json
{"title": "Buy milk", "status": "Pendiente", "priority": "Media", ...}
```

---

### `src/agent/tools/definitions.py` — Tool Functions

**What it does**: Defines what tools the LLM can use AND how to execute them, all in one place. Each function uses LangChain's `@tool` decorator.

**How `@tool` works**: The decorator reads your function's:
- **Docstring** → becomes the tool description (the LLM reads this to decide when to use the tool)
- **Type hints** → become the parameter schema (the LLM knows what arguments to provide)
- **Function body** → the actual code that runs when the LLM calls the tool

Example:
```python
@tool
def create_space(name: str, icon: str = "📁") -> str:
    """Crea un nuevo espacio/contexto para organizar tareas.

    Args:
        name: Nombre del espacio (ej: Universidad).
        icon: Emoji para el espacio (ej: 🎓).
    """
    result = _get_notion().create_space(name=name, icon=icon)
    return json.dumps(result, ensure_ascii=False)
```

This single function replaces what used to be:
1. A JSON schema definition (in the old `definitions.py`)
2. A handler method in `ToolExecutor` (in the old `executor.py`)

**Dependency injection**: `NotionService` is injected at startup via `set_notion_service()`. Tools access it through `_get_notion()`.

**8 tools defined**: `list_spaces`, `create_space`, `get_tasks`, `create_task`, `update_task`, `complete_task`, `delete_task`, `search_tasks`.

---

### `src/agent/prompts/system_prompt.txt` — System Prompt

**What it does**: Defines Oopsie's personality and behavior rules.

**Key rules for the LLM**:
- Always respond in Spanish
- Convert natural language dates to YYYY-MM-DD before calling tools
- Ask for confirmation before deleting tasks
- Ask which space to use if the user doesn't specify
- Be concise and friendly

**Dynamic variable**: `{current_date}` is replaced at runtime with today's date so the LLM knows what "mañana" means.

---

### `src/agent/core.py` — The Agent Brain

**What it does**: Creates and wraps a LangGraph ReAct agent.

**Class `OopsieAgent`**:

On initialization:
1. Creates a `ChatOpenAI` instance pointing to OpenRouter
2. Calls `create_react_agent(model, tools, checkpointer, state_modifier)` — this builds the entire ReAct state machine
3. The `state_modifier` parameter injects our system prompt into every request

**What is `create_react_agent`?**: A LangGraph prebuilt that creates a state machine with two nodes:
- **LLM node**: Sends messages to the model
- **Tools node**: Executes any tool calls the model makes

It automatically routes between them: if the LLM returns tool calls → run tools → send results back to LLM. If the LLM returns text → done.

This replaces the manual loop we used to have (the `for _ in range(MAX_TOOL_ROUNDS)` pattern).

**Conversation memory**: Uses `MemorySaver` (in-memory checkpointer). Each conversation gets a unique `thread_id`. LangGraph stores message history per thread, so the LLM remembers previous messages within a session. Calling `reset()` generates a new thread ID, effectively starting a fresh conversation.

**Why LangGraph over a manual loop?**:
- Built-in state management and checkpointing
- Easy to extend with more nodes/agents later (subtask agent, bibliography search, etc.)
- Better error handling and tool execution
- Battle-tested by the LangChain community

---

### `src/voice/transcriber.py` — Speech-to-Text

**What it does**: Converts audio recordings to text.

**Class `Transcriber`**:
- `__init__(model_size, language)` — Loads the Whisper model. Sizes: `tiny` (fast, less accurate) → `large` (slow, most accurate). `"small"` is a good default.
- `transcribe(audio_path)` → Takes a file path, returns the transcribed text.

**How Faster-Whisper works**: It's an optimized version of OpenAI's Whisper speech recognition model. It runs locally on your CPU (no API calls needed). The `compute_type="int8"` setting uses less memory at the cost of minimal accuracy loss.

---

### `src/interface/app.py` — Gradio UI

**What it does**: Creates the web interface. This is intentionally a thin layer — it only handles UI events and delegates everything to the agent.

**Function `create_app(agent, transcriber)`**:

Creates a Gradio Blocks app with:
- **Chatbot**: Shows conversation history
- **Text input + Send button**: For typing messages
- **Audio input**: For voice recording (microphone)
- **New conversation button**: Clears history

**Event handlers**:
- `handle_text()` → Sends text to `agent.process_message()`, updates chat
- `handle_audio()` → Transcribes audio via `transcriber.transcribe()`, then sends text to agent
- `reset_chat()` → Calls `agent.reset()`, clears UI

**Why it's thin**: All logic lives in the agent and Notion layers. If you want to replace Gradio with Angular+Ionic or any other frontend, you only need to call `agent.process_message(text)` — nothing else changes.

---

### `scripts/setup.py` — Initial Setup

**What it does**: Creates the "Oopsie Hub" root page in Notion on first run.

**Flow**:
1. Load API key from `.env`
2. Verify the key works (calls Notion API)
3. Check if Oopsie Hub already exists (by ID or search)
4. If not found (or `--force` flag), create the root page
5. Save the page ID to `.env` for future use

**Why a separate script**: You only run this once. It's not part of the app runtime. Keeping it separate avoids mixing one-time setup with application code.

---

## Data Flow: What Happens When You Send a Message

Here's a complete trace of what happens when you type "Crea una tarea: estudiar para el examen, para mañana, prioridad alta" in the University space:

```
1. Gradio UI
   └─ handle_text("Crea una tarea: estudiar para el examen...")
       └─ agent.process_message("Crea una tarea: estudiar para el examen...")

2. OopsieAgent
   └─ Calls graph.invoke({"messages": [("user", "...")]}, config)

3. LangGraph ReAct Loop
   └─ LLM Node: sends messages + tools to ChatOpenAI → OpenRouter → Kimi K2.5
   └─ LLM decides to call create_task tool
   └─ Tools Node: executes create_task @tool function

4. @tool create_task
   └─ Calls _get_notion().create_task(space_id, title, due_date, priority)

5. NotionService
   └─ Calls Notion API → Creates page in the University database
   └─ Returns: {id: "...", title: "Estudiar para el examen", ...}

6. LangGraph ReAct Loop (continues)
   └─ Tool result sent back to LLM Node
   └─ LLM generates final text (no more tool calls)
   └─ Returns: "¡Listo! He creado la tarea..."

7. OopsieAgent
   └─ Extracts last message content from graph result

8. Gradio UI
   └─ Displays the response in the chat
```

---

## Key Concepts

### Tool Calling (Function Calling)

The most important pattern in this project. Instead of the LLM trying to generate API calls as text (unreliable), we give it a structured menu of functions it can call. The LLM returns structured JSON, and LangGraph executes it safely.

This is what makes Oopsie an **agent** rather than a simple chatbot — it can take actions in the real world (Notion).

### ReAct Pattern (Reason + Act)

The agent follows a loop: **Reason** (think about what to do) → **Act** (call a tool) → **Observe** (read the result) → repeat until done. LangGraph's `create_react_agent` implements this automatically. You don't write the loop — you just provide the model and tools.

### Separation of Concerns

Each module has one job:
- `NotionService` → talks to Notion (knows nothing about LLMs or LangChain)
- `@tool functions` → bridge between LLM and Notion (call NotionService methods)
- `OopsieAgent` → wraps the LangGraph agent (knows nothing about Notion details)
- `app.py` → displays things on screen (knows nothing about LLMs or Notion)

This means you can change any layer without affecting the others.

### The System Prompt

The system prompt is the "personality configuration" of the LLM. It defines:
- How Oopsie talks (informal Spanish)
- What rules to follow (ask before deleting, etc.)
- What format to use for dates

It's loaded from a text file so you can tweak the personality without touching code. In LangGraph, it's passed via `state_modifier` to `create_react_agent`.

### Why LangGraph

LangGraph gives us infrastructure for free:
- **Checkpointing**: Conversation memory without manual history management
- **Multi-agent support**: When we add specialized agents later (subtask management, URL bibliographies), LangGraph makes it easy to orchestrate multiple agents
- **State machines**: Complex flows (confirmation dialogs, multi-step operations) can be modeled as graph nodes and edges
- **Streaming**: Built-in support for streaming responses to the UI

### Why OpenRouter Instead of OpenAI Directly

OpenRouter is a proxy that gives access to many models through one API. Benefits:
- Can switch between models (Kimi K2.5, Claude, GPT, etc.) by changing one config value
- Uses the same OpenAI SDK format — LangChain's `ChatOpenAI` works with just a `base_url` change
- Often cheaper than direct API access
