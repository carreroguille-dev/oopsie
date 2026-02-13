# Test: Conversation History Limit (10 messages)

Send these 13 messages **one by one** to the Telegram bot.
Messages 1-10 fill the history window. Messages 11-13 trigger trimming
and verify the agent still works correctly.

---

## Phase 1 — Fill the history (messages 1-6)

### Message 1 — Create a space
```
Crea un espacio llamado Trabajo
```
> Expected: confirms space created.

### Message 2 — Create a task (triggers tool calls)
```
Apunta en Trabajo que tengo que enviar el informe mensual para el viernes, prioridad alta
```
> Expected: confirms task created with due date and priority Alta.

### Message 3 — Create another task
```
Agrega en Trabajo: reunión con el equipo para mañana, prioridad media
```
> Expected: confirms second task created.

### Message 4 — List tasks (verify both exist)
```
Qué tareas tengo en Trabajo?
```
> Expected: lists both tasks (informe mensual + reunión).

### Message 5 — Multi-step: task with follow-up
```
Apunta que tengo que comprar leche
```
> Expected: asks which space to save the task in.

### Message 6 — Follow-up answer
```
En Trabajo
```
> Expected: confirms task saved in Trabajo. This tests the context bug fix
> (the agent must read "En Trabajo" as the space selection, not re-process message 5).

---

## Phase 2 — Approach the limit (messages 7-10)

### Message 7 — Search
```
Busca la tarea de la leche
```
> Expected: finds the "comprar leche" task.

### Message 8 — Complete a task
```
Marca como completada la tarea de la leche
```
> Expected: confirms task completed.

### Message 9 — Create a new space
```
Crea un espacio llamado Personal
```
> Expected: confirms space created.

### Message 10 — Cross-space task
```
Agrega en Personal: llamar al dentista para la semana que viene, prioridad baja
```
> Expected: confirms task created in Personal.

---

## Phase 3 — Trimming active (messages 11-13)

At this point the history has well over 10 messages (user + AI + tool
messages). Trimming should kick in after each turn.

### Message 11 — Verify recent context survives trimming
```
Qué espacios tengo?
```
> Expected: lists Trabajo and Personal. The agent still knows about both
> even though early messages were trimmed — the spaces exist in Notion
> regardless of chat history.

### Message 12 — Verify tool pairs are intact
```
Qué tareas pendientes tengo en Trabajo?
```
> Expected: lists remaining pending tasks (informe mensual, reunión).
> "Comprar leche" should show as completed or not appear if filtering
> by pending. No errors about orphaned tool calls.

### Message 13 — New task after trimming
```
Agrega en Personal: comprar regalo de cumpleaños para el sábado, prioridad urgente
```
> Expected: confirms task created normally. This proves the agent
> functions correctly after multiple rounds of trimming.

---

## What to watch for

| Check | Pass criteria |
|-------|--------------|
| Message 6 context | Agent reads "En Trabajo" as space selection, does NOT re-ask |
| No errors in logs | No `tool_call_id` mismatch or orphaned ToolMessage errors |
| Messages 11-13 work | Agent responds normally after trimming kicks in |
| Tool calls still work | Tasks are actually created/listed in Notion |
