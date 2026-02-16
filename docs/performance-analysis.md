# Performance Analysis — Oopsie Telegram Bot

**Date:** 2026-02-16

---

## Current State

- **Response time:** 7-35 seconds per message
- **Model:** `moonshotai/kimi-k2.5` via OpenRouter
- **Recent optimizations:** `max_tokens` reduced to 512, logging added, history truncated to 10 messages

---

## Critical Bottlenecks Identified

### 1. LLM Round-Trips (BIGGEST ISSUE)

- **Complex flow:** 4 sequential LLM calls = 12-20 seconds
  - Call 1: `list_spaces()` (3-5s)
  - Call 2: Process spaces, ask user (3-5s)
  - Call 3: `create_task()` (3-5s)
  - Call 4: Generate response (3-5s)
- **Problem:** Agent calls `list_spaces()` on almost every turn to resolve space names to UUIDs

### 2. Model Selection

- **Current:** Kimi K2.5 = 3-5s per call (double proxy: App -> OpenRouter -> Moonshot)
- Has hidden reasoning tokens (30-91 extra tokens per call, billed but invisible)
- Overqualified for simple tool routing

**Faster alternatives:**
- `google/gemini-2.0-flash`: ~1-2s (60% faster)
- `anthropic/claude-haiku-3.5`: ~1-2s
- `openai/gpt-4o-mini`: ~1-2s

### 3. Token Budget

- **2,500 tokens per request** (measured in production)
  - System prompt: 441 tokens (already optimized)
  - Tool definitions: 317 tokens (reasonable)
  - History: 1000-1500 tokens (truncated)

**Finding:** Token count is NOT the problem. The issue is the number of calls and model speed.

### 4. Space Cache Not Integrated

- File `src/cache/space_cache.py` exists with full implementation
- **BUT:** Not connected to the agent!
- Agent still calls `list_spaces()` every turn (adds 2 extra LLM round-trips)

### 5. Startup Delays

- **LangGraph import:** 1.75s
- **Whisper import:** 3.84s (blocks startup)
- **`ensure_space_properties()`:** 1.5-2.5s (called for each space synchronously in main.py:48-52)
- **Total startup:** ~6 seconds before first message

### 6. No Streaming

- Uses `graph.invoke()` (blocking)
- User waits in silence until complete response arrives
- Could use `graph.stream()` for progressive updates

---

## Optimization Plan (Prioritized by Impact)

| Priority | Optimization | Impact | Effort | Risk |
|----------|-------------|--------|--------|------|
| **O1** | Switch to Gemini 2.0 Flash | 60% faster per call | LOW (config change) | LOW |
| **O2** | Integrate space cache in system prompt | Eliminates 2 LLM round-trips | MEDIUM (4-6 hrs) | LOW |
| **O5** | Stream responses to Telegram | Perceived latency <2s | MEDIUM-HIGH (6-8 hrs) | MEDIUM |
| **O6** | Lazy load Whisper | Startup -3.8s | LOW (30 min) | LOW |
| **O7** | Background `ensure_space_properties()` | Startup -1.5s | LOW (30 min) | LOW |

---

## Detailed Recommendations

### O1: Switch Model (15 minutes, 60% faster immediately)

**File:** `config/config.yaml`

```yaml
llm:
  model: "google/gemini-2.0-flash"  # Was: moonshotai/kimi-k2.5
  base_url: "https://openrouter.ai/api/v1"
  temperature: 0.7
  max_tokens: 512
```

**Testing:** Run 10-20 test messages, verify tool calling quality remains high.

---

### O2: Integrate Space Cache (4-6 hours, eliminates 2 round-trips)

**Problem:** Space cache exists but isn't used. Agent still calls `list_spaces()` every turn.

**Files to modify:**

1. **`src/main.py:48-55`** — Initialize and inject cache

```python
from src.cache.space_cache import SpaceCache

# After notion = NotionService(...)
space_cache = SpaceCache(notion, ttl=1800)
space_cache.load()

agent = OopsieAgent(
    model=llm_cfg["model"],
    api_key=config["openrouter"]["api_key"],
    base_url=llm_cfg["base_url"],
    temperature=llm_cfg["temperature"],
    max_tokens=llm_cfg["max_tokens"],
    space_cache=space_cache,
)
```

2. **`src/agent/core.py:29-30`** — Accept cache parameter

```python
def __init__(self, model, api_key, base_url,
             temperature=0.7, max_tokens=2048,
             user_id=None, space_cache=None):
    self._space_cache = space_cache
```

3. **`src/agent/core.py:21-25`** — Inject spaces into prompt

```python
def _build_system_prompt(space_cache=None):
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d (%A)")

    spaces_section = ""
    if space_cache:
        spaces_section = "\n\n# ESPACIOS DISPONIBLES\n"
        for name, uuid in space_cache.spaces.items():
            spaces_section += f"- {name}: {uuid}\n"

    return template.format(current_date=today) + spaces_section
```

4. **`src/agent/prompts/system_prompt.txt:8`** — Update instructions

```diff
- Si el usuario NO especifica espacio: llama a list_spaces y pregunta cual usar
+ Si el usuario NO especifica espacio: consulta la seccion ESPACIOS DISPONIBLES y pregunta cual usar
```

5. **`src/agent/prompts/system_prompt.txt:25`** — Update tool rules

```diff
- Para obtener un space_id: llama a list_spaces primero.
+ Para obtener un space_id: consulta la seccion ESPACIOS DISPONIBLES arriba.
```

6. **`src/agent/tools/definitions.py:65`** — Invalidate cache on create

```python
@tool
def create_space(name, icon=""):
    logger.info("Tool create_space called with name='%s', icon='%s'", name, icon)
    result = _safe(_get_notion().create_space, name=name, icon=icon)
    # Invalidate cache after creating a new space
    return result
```

**Impact:**
- Simple task: 7-10s -> **2-4s**
- Complex task: 15-25s -> **5-8s**

---

### O5: Stream Responses (6-8 hours, perceived latency <2s)

**Files:** `src/agent/core.py`, `src/interface/bot.py`

**New method in core.py:**

```python
def stream_message(self, user_message):
    config = {"configurable": {"thread_id": self._thread_id}}

    if self._langfuse_enabled:
        handler = self._create_langfuse_handler()
        config["callbacks"] = [handler]
        config["metadata"] = self._langfuse_metadata()

    last_content = ""
    for event in self.graph.stream(
        {"messages": [("user", user_message)]},
        config=config,
        stream_mode="values",
    ):
        if messages := event.get("messages"):
            response = self._extract_response(messages)
            if response and response != last_content:
                last_content = response
                yield response

    result = self.graph.get_state(config)
    self._trim_history(config, result.values["messages"])
```

**Update bot.py handle_text:**

```python
async def handle_text(update, context):
    text = update.message.text
    if not text or not text.strip():
        return

    user_id = update.effective_user.id
    logger.info("Text message received from user_id=%s", user_id)

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        msg = await update.message.reply_text("Processing...")

        last_response = ""
        last_edit_time = time.time()
        MIN_EDIT_INTERVAL = 0.5  # Avoid Telegram rate limits

        for partial in agent.stream_message(text):
            now = time.time()
            if (now - last_edit_time) >= MIN_EDIT_INTERVAL:
                await msg.edit_text(partial)
                last_edit_time = now
                last_response = partial

        if partial != last_response:
            await msg.edit_text(partial)

        logger.info("Response streamed to user_id=%s", user_id)
    except Exception as e:
        logger.error("Failed to handle text message", exc_info=True)
        await update.message.reply_text("Lo siento, ocurrio un error.")
```

---

### O6: Lazy Load Whisper (30 minutes, -3.8s startup)

**File:** `src/main.py:73-83`

```python
transcriber = None

def get_transcriber():
    global transcriber
    if transcriber is None:
        try:
            voice_cfg = config.get("voice", {})
            transcriber = Transcriber(
                model_size=voice_cfg.get("model_size", "small"),
                language=voice_cfg.get("language", "es"),
            )
            logger.info("Whisper loaded on-demand")
        except Exception as e:
            logger.warning("Voice transcription unavailable: %s", e)
    return transcriber
```

**File:** `src/interface/bot.py:111-114`

```python
async def handle_voice(update, context):
    user_id = update.effective_user.id
    logger.info("Voice message received from user_id=%s", user_id)

    transcriber = get_transcriber()
    if not transcriber:
        await update.message.reply_text("El reconocimiento de voz no esta disponible.")
        return
    # ... rest of code
```

---

### O7: Background Space Verification (30 minutes, -1.5s startup)

**File:** `src/main.py:46-54`

```python
import threading

def verify_spaces_async(notion_service):
    try:
        spaces = notion_service.list_spaces()
        logger.info("Found %d existing space(s)", len(spaces))
        for space in spaces:
            notion_service.ensure_space_properties(space["id"])
        logger.info("Space properties verified in background")
    except Exception as e:
        logger.warning("Background space verification failed: %s", e)

thread = threading.Thread(
    target=verify_spaces_async,
    args=(notion,),
    daemon=True
)
thread.start()
```

---

## Expected Results

| Scenario | Current | After O1 | After O1+O2 | After All |
|----------|---------|----------|-------------|-----------|
| Startup time | 6s | 6s | 6s | **2.5s** |
| Simple task (space given) | 7-10s | 3-5s | 2-4s | **1-2s perceived** |
| Complex task (space not given) | 15-25s | 7-12s | 5-8s | **2-3s perceived** |
| List tasks | 7-10s | 3-5s | 2-4s | **1-2s perceived** |
| Search | 10-15s | 5-7s | 3-5s | **2-3s perceived** |

**Total improvement: 75-80% faster response times** + streaming for near-instant perceived feedback.

---

## Implementation Phases

### Phase 1: Quick Wins (2-3 hours, 50-60% faster)

1. O1: Switch to Gemini 2.0 Flash (15 min)
2. O6: Lazy load Whisper (30 min)
3. O7: Background space verification (30 min)

Deploy, test for 1-2 days, measure with Langfuse.

### Phase 2: Structural (1-2 days, 75-80% faster)

4. O2: Integrate space cache (4-6 hours)

Deploy, test thoroughly.

### Phase 3: UX Polish (2-3 days, perceived <2s)

5. O5: Streaming responses (6-8 hours)

---

## Tracking Metrics

Add timing to `src/agent/core.py:104-127`:

```python
import time

def process_message(self, user_message):
    start_time = time.time()
    logger.debug("Processing message (length=%d chars)", len(user_message))

    # ... existing code ...

    elapsed = time.time() - start_time
    logger.info("Message processed in %.2fs, response length=%d chars",
                elapsed, len(response))
    return response
```

**Monitor in Langfuse:** Average processing time, P95 latency, LLM calls per turn.

---

## Key Files Reference

| File | Relevance |
|------|-----------|
| `config/config.yaml` (line 4) | Model config |
| `src/agent/core.py` (lines 21-46, 104-127) | Prompt building, processing |
| `src/agent/prompts/system_prompt.txt` (lines 8, 25) | Space instructions |
| `src/main.py` (lines 48-54, 73-83) | Space verification, Whisper init |
| `src/cache/space_cache.py` | Ready to integrate |
| `src/interface/bot.py` (lines 88-105) | Message handling |
| `src/notion/client.py` (lines 48-64) | list_spaces, 200-300ms each |
| `src/agent/tools/definitions.py` (lines 43-52, 56-64) | Tool definitions |

---

## Conclusion

The bottleneck is **not token count or prompt size** (already optimized). The real issues are:

1. Too many LLM round-trips (2-4 per turn)
2. Slow model (Kimi K2.5 = 3-5s per call)
3. Space cache exists but isn't used
4. No streaming = poor UX

**Recommendation:** Start with Phase 1 (quick wins), measure results, then proceed to Phase 2. This will get you from 15-25s to 2-5s response times with moderate effort.
