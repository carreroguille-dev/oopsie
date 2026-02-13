# Performance Analysis — Agent Response Time

**Current average:** 7-35 seconds per message
**Target:** < 5 seconds for simple operations
**Date:** 2026-02-13

---

## 1. LLM API Calls per Message (BIGGEST BOTTLENECK)

A single user request triggers **2-4 sequential LLM round-trips** through OpenRouter:

### Simple flow (user specifies space): 2 round-trips

| Round-trip | Action                        | ~Tokens (in/out) | ~Latency |
|------------|-------------------------------|-------------------|----------|
| 1st        | LLM decides to call a tool    | 2700 / 150        | 3-5s     |
| 2nd        | LLM reads result, writes reply| 2600 / 100        | 3-5s     |
| **Total**  |                               |                   | **6-10s**|

### Complex flow (space not specified): 4 round-trips

| Round-trip | Action                          | ~Tokens (in/out) | ~Latency |
|------------|---------------------------------|-------------------|----------|
| 1st        | LLM calls `list_spaces`         | 2500 / 50         | 3-5s     |
| 2nd        | LLM reads spaces, asks user     | 2700 / 100        | 3-5s     |
| 3rd        | LLM calls `create_task`         | 2800 / 150        | 3-5s     |
| 4th        | LLM reads result, writes reply  | 2600 / 100        | 3-5s     |
| **Total**  |                                 |                   | **12-20s**|

Each round-trip is a full HTTP request through: App -> OpenRouter -> Model provider -> back.

---

## 2. Model Selection: `moonshotai/kimi-k2.5`

**Current model:** `moonshotai/kimi-k2.5` via OpenRouter

### Problems

- **Double proxy:** Request travels App -> OpenRouter -> Moonshot AI, adding routing
  overhead on top of inference latency.
- **Hidden reasoning tokens:** The model produces `reasoning_tokens` (30-91 per call)
  that are billed and add latency but are invisible to the application. This is
  chain-of-thought the model does internally before responding.
- **Overqualified:** This is a large reasoning model being used for simple tool routing
  ("user said 'Trabajo', pick the matching space_id"). A smaller, faster model can
  handle this with equal accuracy.

### Faster alternatives (via OpenRouter)

| Model                           | Avg latency (tool call) | Cost     |
|---------------------------------|-------------------------|----------|
| `google/gemini-2.0-flash`       | ~1-2s                   | Very low |
| `anthropic/claude-haiku-3.5`    | ~1-2s                   | Low      |
| `openai/gpt-4o-mini`            | ~1-2s                   | Low      |
| `moonshotai/kimi-k2.5` (current)| ~3-5s                   | Low      |

**Estimated impact:** Switching model alone could cut per-call latency by 50-70%.

---

## 3. Conversation History Payload

From production traces, `prompt_tokens` per call range from **2,387 to 2,781**.

### Token budget breakdown (approximate)

| Component                | Tokens   | Notes                                       |
|--------------------------|----------|---------------------------------------------|
| Tool definitions (8 tools)| 800-1000 | Fixed cost every call. Verbose docstrings.  |
| Conversation history     | 1000-1500| 10-message window after trimming.           |
| System prompt            | ~200     | Already lean.                               |
| New user message         | 20-50    | Negligible.                                 |
| **Total**                | **~2500**|                                             |

### Observations

- **Tool definitions are the biggest fixed cost.** The 8 tool docstrings contain
  repetitive instructions (e.g., "DEBE obtenerse llamando a list_spaces primero"
  appears in 4 tools). These could be consolidated.
- **History is bounded** at 10 messages thanks to the sliding window, so it won't
  grow unbounded. This is already optimized.
- **System prompt** at ~200 tokens is concise. No action needed.

---

## 4. Tool Execution Latency (Notion API)

Each Notion API call adds **200-500ms** of network latency. This is minor compared
to LLM round-trips but compounds in multi-tool flows.

### Per-tool latency estimates

| Tool            | Notion calls | ~Latency | Frequency          |
|-----------------|--------------|----------|--------------------|
| `list_spaces`   | 1            | 200-300ms| Very high (almost every turn) |
| `create_space`  | 1            | 300-500ms| Rare               |
| `get_tasks`     | 1            | 200-400ms| High               |
| `create_task`   | 1            | 300-500ms| High               |
| `update_task`   | 1            | 200-400ms| Medium             |
| `complete_task` | 1            | 200-400ms| Medium             |
| `delete_task`   | 1            | 200-300ms| Rare               |
| `search_tasks`  | 1            | 300-500ms| Low                |

### Key issue: `list_spaces` is called almost every turn

The system prompt and tool docstrings instruct the agent to "ALWAYS call
`list_spaces` first" to resolve space names to UUIDs. This adds:

- 200-300ms for the Notion API call
- A full extra LLM round-trip (3-5s) to process the result

Spaces rarely change during a session. This data could be cached.

---

## 5. System Prompt Size

The system prompt (`src/agent/prompts/system_prompt.txt`) is **30 lines, ~200 tokens**.
It is already concise and well-structured. No optimization needed here.

---

## 6. Agent Architecture: Unnecessary Round-Trips

### The `list_spaces` problem

The agent is instructed to call `list_spaces` before any space-related operation.
Even when the user explicitly names a space ("Agrega en Trabajo: ..."), the agent
must still:

1. Call `list_spaces` (LLM round-trip #1 + Notion API call)
2. Read the result and match "Trabajo" to a UUID (LLM round-trip #2)
3. Call the actual tool (LLM round-trip #3)
4. Read the result and respond (LLM round-trip #4)

If the agent already knew the space names and UUIDs (injected into the system
prompt or cached), steps 1-2 would be eliminated entirely.

### `max_tokens: 2048` is excessive

Agent responses are never longer than ~150 tokens. Some model providers allocate
compute resources proportional to `max_tokens`. Reducing to 512 would be safe and
may reduce latency marginally.

---

## Optimization Plan (Ranked by Impact)

### O1. Switch to a faster model
- **Impact:** ~50-70% faster inference per round-trip
- **Effort:** Config change (`config.yaml`)
- **Risk:** Low — the task is simple tool routing, not complex reasoning
- **Action:** Change `model` to `google/gemini-2.0-flash` or `anthropic/claude-haiku-3.5`

### O2. Cache spaces and inject into system prompt
- **Impact:** Eliminates 2 LLM round-trips on most turns (saves 6-10s)
- **Effort:** Medium
- **Risk:** Low — cache invalidates on create/delete space
- **Action:**
  1. Load spaces at startup and cache in `OopsieAgent`
  2. Inject space list (name + UUID) into the system prompt
  3. Invalidate cache when `create_space` or `delete_task` is called
  4. Remove "always call list_spaces first" instructions from prompt and tool docs

### O3. Trim tool docstrings
- **Impact:** ~300 fewer tokens per request (~10-15% reduction)
- **Effort:** Easy
- **Risk:** None — remove only redundant instructions
- **Action:** Remove repeated "DEBE obtenerse llamando a list_spaces" from each
  tool. Consolidate shared instructions into the system prompt or a single note.

### O4. Reduce `max_tokens` to 512
- **Impact:** Minor latency improvement (model-dependent)
- **Effort:** Config change
- **Risk:** None — responses never exceed ~200 tokens
- **Action:** Change `max_tokens` in `config.yaml`

### O5. Stream responses to Telegram
- **Impact:** Perceived latency drops significantly (user sees text appearing)
- **Effort:** Medium-High
- **Risk:** Low — Telegram supports message editing for progressive updates
- **Action:**
  1. Use `graph.stream()` instead of `graph.invoke()`
  2. Send initial message on first token
  3. Edit message as more tokens arrive (throttle edits to avoid rate limits)

---

## Expected Results

| Scenario                     | Current  | After O1   | After O1+O2 | After all |
|------------------------------|----------|------------|-------------|-----------|
| Simple task (space given)    | 7-10s    | 3-5s       | 2-3s        | 1-2s      |
| Task (space not given)       | 15-25s   | 7-12s      | 3-5s        | 2-3s      |
| List tasks                   | 7-10s    | 3-5s       | 2-3s        | 1-2s      |
| Search                       | 10-15s   | 5-7s       | 3-5s        | 2-3s      |
