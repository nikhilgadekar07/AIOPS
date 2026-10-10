import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parent.parent
AI_AGENTS = Path(__file__).resolve().parent
sys.path.insert(0, str(AI_AGENTS))

from orchestrator.db import engine, init_db
from orchestrator.entities import Requirement
from agents.ambiguity_agent import detect_ambiguities

init_db()

app = FastAPI(title="AIOPS UI")

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AIOPS AI Builder</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        background: #0b1220;
        color: #e5e7eb;
        margin: 0;
        padding: 28px;
      }
      .container { max-width: 1200px; margin: 0 auto; }
      .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
      }
      .topbar h1 { margin: 0; font-size: 2rem; }
      .badge {
        background: rgba(59,130,246,0.15);
        color: #93c5fd;
        border: 1px solid #3b82f6;
        border-radius: 999px;
        padding: 8px 12px;
        font-size: 12px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }
      .panel {
        background: #111827;
        border: 1px solid #243244;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.35);
      }
      .main-grid {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 20px;
      }
      .field-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin-bottom: 16px;
      }
      textarea, input, button, select {
        width: 100%;
        box-sizing: border-box;
        margin-top: 10px;
        padding: 12px 14px;
        border-radius: 10px;
        border: 1px solid #334155;
        background: #0f172a;
        color: white;
        font-size: 14px;
      }
      button {
        cursor: pointer;
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        border: none;
        font-weight: bold;
      }
      .button-row {
        display: flex;
        gap: 10px;
        margin-top: 16px;
      }
      .button-row button.secondary { background: #16a34a; }
      .button-row button.ghost {
        background: transparent;
        border: 1px solid #475569;
      }
      .status { margin-top: 12px; color: #93c5fd; font-weight: bold; }
      .status-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
        margin-top: 18px;
      }
      .status-topline {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        margin-bottom: 10px;
        font-weight: 700;
      }
      .progress-track {
        width: 100%;
        height: 12px;
        background: #0f172a;
        border-radius: 999px;
        overflow: hidden;
        border: 1px solid #475569;
      }
      .progress-bar {
        width: 0%;
        height: 100%;
        background: linear-gradient(90deg, #22c55e, #38bdf8, #a78bfa);
        border-radius: inherit;
        transition: width 0.4s ease;
      }
      .activity-list {
        list-style: none;
        padding-left: 0;
        margin: 12px 0 0 0;
      }
      .activity-list li {
        margin-bottom: 8px;
        padding: 10px 12px;
        background: rgba(15, 23, 42, 0.85);
        border-left: 3px solid #3b82f6;
        border-radius: 8px;
        color: #dbeafe;
      }
      .review-panel { display: none; }
      .review-panel.visible { display: block; }
      .review-box {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 14px;
        margin-top: 12px;
      }
      .execution-log {
        background: #020817;
        border: 1px solid #243244;
        border-radius: 12px;
        padding: 16px;
        margin-top: 12px;
        max-height: 360px;
        overflow: auto;
      }
      .artifact-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 14px;
      }
      .artifact-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 12px;
      }
      .artifact-path {
        color: #93c5fd;
        font-size: 12px;
        word-break: break-word;
      }
      .clarification-panel { display: none; }
      .clarification-panel.visible { display: block; }
      .question-field { display: block; margin-top: 16px; color: #e5e7eb; }
      .question-field textarea { min-height: 82px; resize: vertical; }
      .preview-frame { width: 100%; min-height: 720px; border: 1px solid #334155; border-radius: 8px; background: white; margin-top: 16px; }
      .build-result { color: #dbeafe; padding: 18px 0 4px; white-space: pre-wrap; }
      .output-title { display: flex; align-items: center; gap: 14px; min-width: 0; }
      .preview-link { color: #a5f3fc; font-size: 14px; font-weight: 700; text-decoration: none; white-space: nowrap; }
      .preview-link:hover { text-decoration: underline; }
      pre {
        white-space: pre-wrap;
        margin: 0;
        color: #dbeafe;
      }
      @media (max-width: 900px) { .main-grid, .field-grid { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="topbar">
        <h1>AIOPS Builder</h1>
        <div class="badge">Human in the loop</div>
      </div>

      <div class="main-grid">
        <div class="panel">
          <h2>Describe the build</h2>
          <p style="color:#cbd5e1; margin-top: 8px;">Tell the system what to create, improve, or replace. Choose whether it sits on a new project or an existing repo, then allow human review when needed.</p>

          <div class="field-grid">
            <label>
              <strong>Build target</strong>
              <select id="projectMode">
                <option value="new">New project</option>
                <option value="existing">Existing repo / codebase</option>
              </select>
            </label>

            <label>
              <strong>Human review gate</strong>
              <select id="humanReview">
                <option value="auto">Auto-approve after spec review</option>
                <option value="human">Require human review before build</option>
              </select>
            </label>
          </div>

          <div id="repoSection" style="display:none; margin-bottom: 16px;">
            <label>
              <strong>Repository or workspace location</strong>
              <input id="repoLocation" type="text" placeholder="GitHub URL, local repo path, or .zip file" />
            </label>
          </div>

          <textarea id="prompt" rows="9" placeholder="Example: Build a customer support dashboard with a sidebar, ticket list, status filters, and a create-ticket form."></textarea>

          <div class="button-row">
            <button id="runBtn">Start build</button>
          </div>
          <div id="msg" class="status">Ready when you are.</div>
        </div>

        <div class="panel">
          <div class="status-topline">
            <h2 style="margin:0;">Build activity</h2>
            <span id="livePercent">0%</span>
          </div>
          <div class="progress-track">
            <div id="progressBar" class="progress-bar"></div>
          </div>
          <div class="status-card">
            <div class="status-topline">
              <span id="liveStage">Waiting</span>
            </div>
            <p id="liveMessage" style="margin: 10px 0 0 0; color: #cbd5e1;">The AI is waiting for a request.</p>
            <ul id="activityList" class="activity-list">
              <li>Understanding the request</li>
              <li>Checking for missing details</li>
              <li>Designing the build</li>
              <li>Validating the result</li>
            </ul>
          </div>
        </div>
      </div>

      <div id="reviewPanel" class="panel review-panel">
        <h2>Review before build</h2>
        <div id="reviewSummary" class="review-box"></div>
        <div id="reviewQuestions" class="review-box"></div>
        <div class="button-row">
          <button class="secondary" id="approveReviewBtn">Approve and build</button>
          <button class="ghost" id="modifyReviewBtn">Request changes</button>
          <button class="ghost" id="rejectReviewBtn">Reject</button>
        </div>
      </div>

      <div id="clarificationPanel" class="panel clarification-panel">
        <h2>Before we build</h2>
        <p style="color:#cbd5e1;">Answer these details to shape the result. You can edit or accept the suggested answers.</p>
        <div id="clarificationQuestions"></div>
        <div class="button-row">
          <button id="buildWithAnswersBtn">Build with these answers</button>
          <button class="ghost" id="useDefaultsBtn">Use suggestions</button>
        </div>
      </div>

      <div class="panel">
        <div class="status-topline" style="margin-bottom:0;">
          <div class="output-title"><h2 style="margin:0;">Build output</h2><a id="previewLink" class="preview-link" target="_blank" rel="noopener noreferrer" hidden>Open website ↗</a></div>
          <span id="currentProjectInfo">No active run</span>
        </div>
        <div id="artifactList" class="artifact-list"></div>
        <div id="buildResult" class="build-result">Your finished result will appear here.</div>
        <iframe id="previewFrame" class="preview-frame" title="Generated website preview" sandbox="allow-scripts allow-forms" referrerpolicy="no-referrer" hidden></iframe>
        <div id="executionLog" class="execution-log"><pre>No activity yet. When the build starts, logs will appear here.</pre></div>
      </div>
    </div>

    <script>
      const msg = document.getElementById('msg');
      const liveStage = document.getElementById('liveStage');
      const livePercent = document.getElementById('livePercent');
      const progressBar = document.getElementById('progressBar');
      const liveMessage = document.getElementById('liveMessage');
      const activityList = document.getElementById('activityList');
      const reviewPanel = document.getElementById('reviewPanel');
      const reviewSummary = document.getElementById('reviewSummary');
      const reviewQuestions = document.getElementById('reviewQuestions');
      const executionLog = document.getElementById('executionLog');
      const artifactList = document.getElementById('artifactList');
      const currentProjectInfo = document.getElementById('currentProjectInfo');
      const clarificationPanel = document.getElementById('clarificationPanel');
      const clarificationQuestions = document.getElementById('clarificationQuestions');
      const buildResult = document.getElementById('buildResult');
      const previewFrame = document.getElementById('previewFrame');
      const previewLink = document.getElementById('previewLink');
      let statusPollId = null;
      let pendingBuild = null;
      let activeClarifications = [];
      let lastOutputSignature = null;

      function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
          '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[char]);
      }

      function updateStatusPanel(data = {}) {
        const stage = data.stage || 'Waiting';
        const progress = Math.max(0, Math.min(100, Number(data.progress) || 0));
        const message = data.message || 'The AI is preparing to work on your request.';

        liveStage.textContent = stage;
        livePercent.textContent = `${progress}%`;
        progressBar.style.width = `${progress}%`;
        liveMessage.textContent = message;

        if (Array.isArray(data.stages) && data.stages.length) {
          const recent = data.stages.slice(-4);
          activityList.innerHTML = recent.map(step => `<li>${step.stage}: ${step.message}</li>`).join('');
        } else {
          activityList.innerHTML = `
            <li>Understanding the request</li>
            <li>Checking for missing details</li>
            <li>Designing the build</li>
            <li>Validating the result</li>
          `;
        }
      }

      function startStatusPolling() {
        if (statusPollId) {
          clearInterval(statusPollId);
        }
        statusPollId = setInterval(async () => {
          try {
            const res = await fetch('/api/live-status');
            const data = await res.json();
            updateStatusPanel(data);

            if (data.status === 'completed') {
              clearInterval(statusPollId);
              statusPollId = null;
              msg.textContent = 'Build finished successfully.';
              fetchLatestOutput();
              return;
            }

            if (data.status === 'working') {
              msg.textContent = 'The AI is actively working through your request...';
            }
          } catch (error) {
            // ignore transient polling errors while the pipeline is running
          }
        }, 800);
      }

      function renderReviewPanel(review) {
        reviewPanel.classList.add('visible');
        reviewSummary.innerHTML = `<strong>Summary</strong><br>${escapeHtml(review.summary || 'The request is ready for a human review.')}`;
        reviewQuestions.innerHTML = (review.questions || []).map(item => `
          <div style="margin-top:10px;">
            <strong>${escapeHtml(item.question || 'Review item')}</strong>
            <div style="color:#cbd5e1; margin-top:4px;">${escapeHtml(item.answer || 'No answer supplied yet.')}</div>
          </div>
        `).join('') || '<strong>Review check</strong><div style="color:#cbd5e1; margin-top:4px;">No extra questions generated.</div>';
      }

      function renderClarificationPanel(questions) {
        clarificationPanel.classList.add('visible');
        clarificationQuestions.innerHTML = questions.map((item, index) => `
          <label class="question-field"><strong>${escapeHtml(item.question)}</strong>
            <textarea data-answer-index="${index}">${escapeHtml(item.assumed_default || '')}</textarea>
          </label>
        `).join('');
      }

      function hideClarificationPanel() {
        clarificationPanel.classList.remove('visible');
      }

      function hideReviewPanel() {
        reviewPanel.classList.remove('visible');
      }

      function renderOutputPanel(data) {
        const stages = Array.isArray(data.stages) ? data.stages : [];
        const files = Array.isArray(data.generated_files) ? data.generated_files : [];
        const summary = [
          'Build activity',
          ...stages.map(step => `- ${step.stage}: ${step.message}`),
        ].join('\\n');

        executionLog.querySelector('pre').textContent = summary || 'No activity yet.';
        const validationBody = data.validation?.checks?.[0]?.body;
        buildResult.textContent = validationBody?.summary || validationBody?.message ||
          (data.validation?.status ? `Build validation: ${data.validation.status}.` : 'Build completed.');
        if (data.preview_url) {
          const previewUrl = new URL(data.preview_url, window.location.href).href;
          if (previewFrame.getAttribute('src') !== previewUrl) {
            previewFrame.src = previewUrl;
          }
          if (previewLink.href !== previewUrl) {
            previewLink.href = previewUrl;
          }
          previewLink.hidden = false;
          previewFrame.hidden = false;
        } else {
          previewFrame.removeAttribute('src');
          previewLink.removeAttribute('href');
          previewLink.hidden = true;
          previewFrame.hidden = true;
        }

        if (files.length) {
          artifactList.innerHTML = files.map(fileName => `
            <div class="artifact-card">
              <div><strong>${escapeHtml(fileName)}</strong></div>
              <div class="artifact-path">${escapeHtml(data.workspace_path || data.output_path || 'Generated in project workspace')}</div>
            </div>
          `).join('');
        } else {
          artifactList.innerHTML = '<div class="artifact-card"><strong>No generated files yet.</strong></div>';
        }

        if (data.output_path) {
          currentProjectInfo.textContent = data.output_path;
        } else {
          currentProjectInfo.textContent = 'No active run';
        }
      }

      async function fetchLatestOutput() {
        const res = await fetch('/api/latest');
        const data = await res.json();
        const signature = JSON.stringify(data);
        if (signature === lastOutputSignature) {
          return;
        }
        lastOutputSignature = signature;
        if (data.status === 'no-data') {
          executionLog.innerHTML = '<pre>No activity yet. When the build starts, logs will appear here.</pre>';
          artifactList.innerHTML = '';
          buildResult.textContent = 'Your finished result will appear here.';
          previewFrame.removeAttribute('src');
          previewLink.removeAttribute('href');
          previewLink.hidden = true;
          previewFrame.hidden = true;
          currentProjectInfo.textContent = 'No active run';
          return;
        }
        renderOutputPanel(data);
      }

      function updateProjectModeVisibility() {
        const mode = document.getElementById('projectMode').value;
        const repoSection = document.getElementById('repoSection');
        repoSection.style.display = mode === 'existing' ? 'block' : 'none';
      }

      async function submitBuild(decision, notes = '') {
        const prompt = document.getElementById('prompt').value.trim();
        const projectMode = document.getElementById('projectMode').value;
        const repoLocation = document.getElementById('repoLocation').value.trim();
        const humanReview = document.getElementById('humanReview').value === 'human';

        if (!prompt) {
          msg.textContent = 'Please describe what you want to build.';
          return;
        }

        const payload = {
          prompt,
          project_mode: projectMode,
          mode: projectMode,
          repo_url: repoLocation,
          location: repoLocation,
          require_human_review: humanReview,
          review_decision: decision,
          review_notes: notes,
          clarifications: activeClarifications,
        };

        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
          msg.textContent = data.detail || 'Request failed.';
          return;
        }

        if (data.status === 'review_required') {
          renderReviewPanel(data.review || { summary: data.message, questions: [] });
          return;
        }

        hideReviewPanel();
        msg.textContent = data.message || 'Build started.';
        startStatusPolling();
      }

      async function launchBuild(clarifications) {
        activeClarifications = clarifications;
        hideClarificationPanel();
        const runButton = document.getElementById('runBtn');
        runButton.disabled = true;
        runButton.textContent = 'Building...';
        msg.textContent = 'Build started. The AI is working through the request...';
        updateStatusPanel({ stage: 'Understanding Request', progress: 10, message: 'Preparing the clarified build plan.', stages: [] });
        const payload = {
          prompt: pendingBuild.prompt,
          project_mode: pendingBuild.projectMode,
          mode: pendingBuild.projectMode,
          repo_url: pendingBuild.repoLocation,
          location: pendingBuild.repoLocation,
          require_human_review: pendingBuild.humanReview,
          clarifications,
        };
        try {
          const res = await fetch('/api/run', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
          if (data.status === 'review_required') {
            renderReviewPanel(data.review || { summary: data.message, questions: [] });
            msg.textContent = 'Review the request before implementation starts.';
            return;
          }
          hideReviewPanel();
          msg.textContent = data.message || 'Pipeline started successfully.';
          startStatusPolling();
        } catch (error) {
          msg.textContent = `Build could not start: ${error.message}`;
        } finally {
          runButton.disabled = false;
          runButton.textContent = 'Start build';
        }
      }

      async function answerClarifications(useDefaults = false) {
        const answers = pendingBuild.questions.map((item, index) => {
          const field = clarificationQuestions.querySelector(`[data-answer-index="${index}"]`);
          return { ...item, answer: useDefaults ? item.assumed_default : (field.value.trim() || item.assumed_default) };
        });
        await launchBuild(answers);
      }

      async function runPipeline() {
        const prompt = document.getElementById('prompt').value.trim();
        const projectMode = document.getElementById('projectMode').value;
        const repoLocation = document.getElementById('repoLocation').value.trim();
        const humanReview = document.getElementById('humanReview').value === 'human';

        if (!prompt) {
          msg.textContent = 'Please describe what you want to build.';
          return;
        }

        if (projectMode === 'existing' && !repoLocation) {
          msg.textContent = 'Choose a repo URL, local path, or .zip file for an existing-project build.';
          return;
        }

        const runButton = document.getElementById('runBtn');
        pendingBuild = { prompt, projectMode, repoLocation, humanReview };
        runButton.disabled = true;
        runButton.textContent = 'Checking...';
        hideReviewPanel();
        msg.textContent = 'Checking which details will help shape the result...';
        try {
          const res = await fetch('/api/clarify', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || `Request failed (${res.status}).`);
          pendingBuild.questions = data.questions || [];
          if (pendingBuild.questions.length) {
            renderClarificationPanel(pendingBuild.questions);
            msg.textContent = 'Answer the follow-up questions, or use the suggested answers.';
          } else {
            await launchBuild([]);
          }
        } catch (error) {
          msg.textContent = `Could not prepare the build: ${error.message}`;
        } finally {
          if (!statusPollId) {
            runButton.disabled = false;
            runButton.textContent = 'Start build';
          }
        }
      }

      document.getElementById('projectMode').addEventListener('change', updateProjectModeVisibility);
      document.getElementById('runBtn').addEventListener('click', runPipeline);
      document.getElementById('approveReviewBtn').addEventListener('click', () => submitBuild('approve'));
      document.getElementById('modifyReviewBtn').addEventListener('click', () => submitBuild('modify', 'Please refine the requirements before building.'));
      document.getElementById('rejectReviewBtn').addEventListener('click', () => submitBuild('reject'));
      document.getElementById('buildWithAnswersBtn').addEventListener('click', () => answerClarifications(false));
      document.getElementById('useDefaultsBtn').addEventListener('click', () => answerClarifications(true));
      updateProjectModeVisibility();
      fetchLatestOutput();
      updateStatusPanel();
      setInterval(fetchLatestOutput, 5000);
    </script>
  </body>
</html>
"""


class RunRequest(BaseModel):
    prompt: str | None = None
    description: str | None = None
    title: str | None = None
    mode: str = "new"
    project_mode: str = "new"
    location: str | None = None
    repo_url: str | None = None
    require_human_review: bool = False
    review_decision: str | None = None
    review_notes: str | None = None
    clarifications: list[dict[str, str]] | None = None


class ClarifyRequest(BaseModel):
    prompt: str


class RunResponse(BaseModel):
    status: str
    message: str
    command: str | None = None
    output_path: str | None = None
    review: dict[str, Any] | None = None


def _read_latest_pipeline_output() -> dict[str, Any] | None:
    workspace_dir = AI_AGENTS / "workspace"
    workspace_dir.mkdir(exist_ok=True, parents=True)
    # live_status.json is runtime state, not a completed pipeline result.
    # Selecting it here makes the UI lose the generated files after completion.
    files = sorted(workspace_dir.glob("pipeline_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_start_status(prompt: str) -> None:
    status_path = AI_AGENTS / "workspace" / "live_status.json"
    status_path.parent.mkdir(exist_ok=True, parents=True)
    status_path.write_text(
        json.dumps(
            {
                "status": "working",
                "stage": "Starting build",
                "message": "The build process has started. Preparing the workspace...",
                "progress": 5,
                "requirement_id": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "stages": [
                    {
                        "stage": "Starting build",
                        "message": "The build process has started. Preparing the workspace...",
                    }
                ],
                "prompt": prompt,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _watch_pipeline(process: subprocess.Popen, log_path: Path, prompt: str) -> None:
    return_code = process.wait()
    if return_code == 0:
        return

    try:
        details = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    except OSError:
        details = "No process output was captured."

    status_path = AI_AGENTS / "workspace" / "live_status.json"
    status_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "stage": "Build failed",
                "message": f"The build process stopped with exit code {return_code}. {details}".strip(),
                "progress": 0,
                "requirement_id": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "stages": [],
                "prompt": prompt,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=HTML_PAGE)


@app.get("/api/requirements")
async def list_requirements() -> list[dict[str, Any]]:
    with Session(engine) as session:
        items = session.exec(select(Requirement)).all()
        result = []
        for item in items:
            result.append(
                {
                    "requirement_id": item.requirement_id,
                    "title": item.title,
                    "raw_text": item.raw_text,
                    "project_mode": item.project_mode,
                    "workspace_path": item.workspace_path,
                    "status": item.status,
                    "repo_url": item.repo_url,
                    "require_human_review": bool(getattr(item, "require_human_review", False)),
                }
            )
    return result


@app.get("/api/live-status")
async def live_status() -> dict[str, Any]:
    status_path = AI_AGENTS / "workspace" / "live_status.json"
    if not status_path.exists():
        return {"status": "idle", "stage": "Waiting", "message": "The AI is waiting for a request.", "progress": 0, "stages": []}
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
        return payload
    except Exception:
        return {"status": "idle", "stage": "Waiting", "message": "The AI is waiting for a request.", "progress": 0, "stages": []}


@app.get("/api/latest")
async def latest_output() -> dict[str, Any]:
    output = _read_latest_pipeline_output()
    if output is None:
        live_status_payload = await live_status()
        if live_status_payload.get("status") == "idle":
            return {"status": "no-data", "message": "No pipeline output has been created yet."}
        return live_status_payload
    return output


@app.post("/api/clarify")
async def clarify_request(payload: ClarifyRequest) -> dict[str, Any]:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="A natural-language prompt is required.")
    title = " ".join(prompt.split()[:10])
    return {"questions": detect_ambiguities(title, prompt)}


@app.get("/api/preview/{requirement_id}", response_class=HTMLResponse)
async def preview_website(requirement_id: str) -> HTMLResponse:
    with Session(engine) as session:
        requirement = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
    if requirement is None or not requirement.workspace_path:
        raise HTTPException(status_code=404, detail="Generated website not found.")
    workspace_path = Path(requirement.workspace_path).resolve()
    page_path = (workspace_path / "index.html").resolve()
    if not page_path.is_relative_to(workspace_path) or not page_path.is_file():
        raise HTTPException(status_code=404, detail="Generated website not found.")
    return HTMLResponse(content=page_path.read_text(encoding="utf-8"))


@app.get("/api/preview/{requirement_id}/{asset_path:path}")
async def preview_asset(requirement_id: str, asset_path: str) -> FileResponse:
    with Session(engine) as session:
        requirement = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
    if requirement is None or not requirement.workspace_path:
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    workspace_path = Path(requirement.workspace_path).resolve()
    requested_path = (workspace_path / asset_path).resolve()
    if not requested_path.is_relative_to(workspace_path) or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    if requested_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    return FileResponse(requested_path, media_type=mimetypes.guess_type(requested_path.name)[0] or "application/octet-stream")


@app.post("/api/run", response_model=RunResponse)
async def run_pipeline(payload: RunRequest) -> RunResponse:
    prompt = (payload.prompt or payload.description or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="A natural-language prompt is required.")

    project_mode = (payload.project_mode or payload.mode or "new").strip().lower() or "new"
    repo_location = (payload.repo_url or payload.location or "").strip()
    human_review = bool(payload.require_human_review)
    review_decision = (payload.review_decision or "").strip().lower()
    review_notes = (payload.review_notes or "").strip()

    if human_review and not review_decision:
        review = {
            "summary": (
                f"This request is targeting a {project_mode} build and will be created in the workspace. "
                f"The goal is: {prompt}"
            ),
            "questions": [
                {"question": "Does this scope match the target you want built?", "answer": prompt},
                {"question": "Do you want the build to start from a clean project or the existing repo context?", "answer": project_mode},
            ],
        }
        return RunResponse(
            status="review_required",
            message="Human review is required before implementation starts.",
            output_path=str(AI_AGENTS / "workspace"),
            review=review,
        )

    if human_review and review_decision == "reject":
        return RunResponse(
            status="rejected",
            message="The request was rejected by the reviewer.",
            output_path=str(AI_AGENTS / "workspace"),
        )

    if human_review and review_decision == "modify":
        review_notes = review_notes or "The reviewer requested changes before implementation."
        prompt = f"{prompt}\n\nReview feedback: {review_notes}"

    clarifications_json = json.dumps(payload.clarifications) if payload.clarifications is not None else None

    cmd = [
        sys.executable,
        str(AI_AGENTS / "run_full_pipeline.py"),
        "--prompt",
        prompt,
        "--mode",
        project_mode,
    ]
    if human_review:
        cmd.append("--require-human-review")
    else:
        cmd.append("--auto-approve")
    if repo_location and project_mode == "existing":
        cmd.extend(["--location", repo_location])
    if clarifications_json is not None:
      cmd.extend(["--clarifications", clarifications_json])

    cwd = str(ROOT)
    _write_start_status(prompt)
    log_path = AI_AGENTS / "workspace" / f"pipeline_{uuid.uuid4().hex}.log"
    log_handle = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            creationflags=0,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        log_handle.close()
        raise HTTPException(status_code=500, detail=f"Could not start build process: {exc}") from exc

    threading.Thread(
        target=lambda: (_watch_pipeline(process, log_path, prompt), log_handle.close()),
        daemon=True,
    ).start()

    message = "Pipeline started successfully."
    if project_mode == "existing":
        message += f" Building on the existing repo/workspace at {repo_location or 'the provided location'}."
    else:
        message += " Starting a fresh project build."
    if human_review:
        message += " Human review was acknowledged before the build began."

    return RunResponse(
        status="started",
        message=message,
        command=" ".join(cmd),
        output_path=str(AI_AGENTS / "workspace"),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
