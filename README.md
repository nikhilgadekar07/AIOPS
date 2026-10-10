# AIOPS

AIOPS is an AI-assisted builder that starts from a natural-language idea and turns it into a working implementation.

## Product direction

Instead of forcing the user to enter a rigid title and short description, the system accepts a real-world request in plain language, then tries to understand the actual intent behind it.

The intended flow is:

1. User writes a natural-language request
2. The system interprets the goal and identifies missing details
3. It asks clarifying questions only when needed
4. It decides whether the request fits an existing project, a new app, or a repo patch
5. It builds the implementation and validates the result

This is the real product direction we want to keep: natural-language input, understanding-first workflow, and build-through-validation.

## Core workflow

The current implementation keeps the fundamental stages that matter:

- requirement understanding from a story prompt
- ambiguity detection and clarifying questions
- repository grounding when working in an existing codebase
- grounded specification generation
- critique and confidence checks
- implementation planning
- patch application
- behavior validation

## Current status

The project supports a story-first flow from a natural-language prompt through workspace preparation, specification, implementation, and validation. The active application entry point is `ai-agents/ui_server.py`; the server starts the complete pipeline in `ai-agents/run_full_pipeline.py`.

## Architecture

- ai-agents/orchestrator: database and versioned requirement/spec storage
- ai-agents/input_adapter: workspace preparation
- ai-agents/rag: repo chunking, ingestion, and retrieval
- ai-agents/agents: requirement, spec, and implementation logic
- ai-agents/prompts: LLM prompts for ambiguity, spec generation, critique, and impact analysis

## Important change

The older UI pattern of title + description is intentionally replaced with a single natural-language prompt. The engine still derives a safe internal title behind the scenes, but the user experience is built around the real request text instead of a structured form.

## Run notes

- Local Ollama is used for model access and embeddings
- SQLite is used for saved requirement and spec records
- The project is organized around a natural-language prompt that becomes a requirement internally
- The build pipeline still validates the effect with real execution, not just output text

## Run from a fresh clone

### 1. Clone the repository

```powershell
git clone https://github.com/nikhilgadekar07/AIOPS.git
cd AIOPS
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start Ollama

Install Ollama from [ollama.com](https://ollama.com), then download the models used by the pipeline:

```powershell
ollama pull qwen2.5:3b-instruct
ollama pull nomic-embed-text
```

Make sure Ollama is running at `http://localhost:11434`.

### 5. Start the AIOPS web server

```powershell
python -m uvicorn ai-agents.ui_server:app --host 127.0.0.1 --port 8002 --log-level info
```

Open the application at:

```text
http://127.0.0.1:8002/
```

The first build can take a little longer while Ollama generates the requirement, specification, implementation plan, and validation result.

### 6. Verify the server

Open another PowerShell terminal in the repository folder and run:

```powershell
Invoke-WebRequest http://127.0.0.1:8002/health
```

The response should contain:

```json
{"status":"ok"}
```

### Build output

Generated workspaces, pipeline results, process logs, the local SQLite database, and Chroma data are runtime state. They are intentionally ignored by Git so every clone starts with a clean local workspace.

The repository contains only the active builder path. Legacy command-line flows, duplicate UI files, test-only files, and the old sample application are not included.

## Stop the server

Press `Ctrl+C` in the terminal running Uvicorn.

If port 8002 is already in use, find and stop the listener:

```powershell
$serverPid = (Get-NetTCPConnection -LocalPort 8002 -State Listen).OwningProcess
Stop-Process -Id $serverPid -Force
```
