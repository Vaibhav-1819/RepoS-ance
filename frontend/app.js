/**
 * RepoSéance Frontend Application Logic
 * Manages tab state, repository import, autopsy dashboard, Ghost Chat RAG, and roadmap persistence.
 */

const API_BASE = "http://localhost:8000";

let currentProjectId = null;
let currentProjectData = null;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  checkOllamaStatus();
  loadRecentProjects();
  initImportListeners();
  initChatListeners();
  initRoadmapListeners();
  initSettingsListeners();
});

/* ==========================================================================
   Tab Navigation
   ========================================================================== */
function initTabs() {
  const navBtns = document.querySelectorAll(".nav-btn");
  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      switchTab(targetTab);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));

  const targetBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
  const targetContent = document.getElementById(`tab-${tabId}`);
  if (targetBtn && targetContent) {
    targetBtn.classList.add("active");
    targetContent.classList.add("active");
  }
}

/* ==========================================================================
   Model & Ollama Health Check
   ========================================================================== */
async function checkOllamaStatus() {
  const pill = document.getElementById("ollamaStatusPill");
  const text = document.getElementById("ollamaStatusText");
  try {
    const res = await fetch(`${API_BASE}/api/models/status`);
    if (res.ok) {
      const data = await res.json();
      if (data.is_available && data.is_model_installed) {
        pill.className = "badge status-pill";
        text.innerText = `Local AI: Online (${data.configured_model})`;
      } else if (data.is_available) {
        pill.className = "badge status-pill";
        text.innerText = `Ollama: Ready (Heuristic Fallback)`;
      } else {
        pill.className = "badge status-pill";
        text.innerText = "Offline Mode (Heuristic Active)";
      }
    } else {
      pill.className = "badge status-pill";
      text.innerText = "Offline Mode (Heuristic Active)";
    }
  } catch (err) {
    pill.className = "badge status-pill";
    text.innerText = "Offline Mode (Heuristic Active)";
  }
}

/* ==========================================================================
   Repository Import & Progress Pipeline
   ========================================================================== */
function initImportListeners() {
  const startBtn = document.getElementById("startPathAnalysisBtn");
  const pathInput = document.getElementById("localPathInput");
  const sampleBtn = document.getElementById("loadSampleRepoBtn");
  const dropZone = document.getElementById("zipDropZone");
  const fileInput = document.getElementById("zipFileInput");

  startBtn.addEventListener("click", () => {
    const p = pathInput.value.trim();
    if (!p) {
      alert("Please provide a valid local repository directory path.");
      return;
    }
    summonRepository(p, null);
  });

  sampleBtn.addEventListener("click", () => {
    summonRepository("./sample_abandoned_repo", null);
  });

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      summonRepository(null, e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      summonRepository(null, fileInput.files[0]);
    }
  });
}

async function summonRepository(localPath, zipFile) {
  const pipeline = document.getElementById("pipelineCard");
  const statusMsg = document.getElementById("pipelineStatusMsg");
  pipeline.style.display = "block";

  // Simulate pipeline step states
  setPipelineStep(1, "Validating directory structure...");
  await delay(300);
  setPipelineStep(2, "Applying secret redaction masks...");
  await delay(300);
  setPipelineStep(3, "Inspecting Git commit dormancy and package manifests...");

  const formData = new FormData();
  if (localPath) formData.append("local_path", localPath);
  if (zipFile) formData.append("zip_file", zipFile);

  try {
    setPipelineStep(4, "Building local semantic evidence index...");
    const res = await fetch(`${API_BASE}/api/projects/import`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Séance failed to summon the repository.");
    }

    setPipelineStep(5, "Generating project autopsy and revival roadmap...");
    const data = await res.json();
    currentProjectId = data.project_id;
    currentProjectData = data;

    await delay(400);
    pipeline.style.display = "none";

    renderAutopsy(data);
    loadRecentProjects();
    switchTab("autopsy");

  } catch (err) {
    pipeline.style.display = "none";
    alert(`Error: ${err.message}`);
  }
}

function setPipelineStep(stepNum, msg) {
  for (let i = 1; i <= 5; i++) {
    const el = document.getElementById(`pStep${i}`);
    if (i < stepNum) {
      el.className = "p-step done";
    } else if (i === stepNum) {
      el.className = "p-step active";
    } else {
      el.className = "p-step";
    }
  }
  document.getElementById("pipelineStatusMsg").innerText = msg;
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/* ==========================================================================
   Render Autopsy Dashboard
   ========================================================================== */
function renderAutopsy(projectData) {
  const scan = projectData.scan || {};
  const autopsy = projectData.autopsy || {};
  const git = scan.git || {};

  document.getElementById("autopsyProjectName").innerText = `Project Autopsy: ${projectData.name}`;
  document.getElementById("autopsySourcePath").innerText = `Source: ${projectData.path}`;

  // Metrics
  document.getElementById("metricTotalFiles").innerText = scan.total_files || 0;
  document.getElementById("metricDormantDays").innerText = git.dormant_days || 0;
  document.getElementById("metricTodoCount").innerText = (scan.todos || []).length;
  document.getElementById("metricCommitCount").innerText = git.commit_count || 0;

  // Purpose & Architecture
  document.getElementById("autopsyEngineBadge").innerText = autopsy.inference_engine || "Local AI";
  document.getElementById("autopsyPurposeText").innerText = autopsy.project_purpose || "No purpose reconstructed.";
  document.getElementById("autopsyArchText").innerText = autopsy.architecture_summary || "No architectural overview available.";

  // Entry points chips
  const entryContainer = document.getElementById("autopsyEntryPoints");
  entryContainer.innerHTML = "";
  (autopsy.main_entry_points || []).forEach(ep => {
    const chip = document.createElement("span");
    chip.className = "code-chip";
    chip.innerText = ep;
    entryContainer.appendChild(chip);
  });

  // Languages & Manifests
  const langContainer = document.getElementById("autopsyLanguagesList");
  langContainer.innerHTML = "";
  (scan.languages || []).forEach(([lang, count]) => {
    const item = document.createElement("div");
    item.className = "sub-item";
    item.innerHTML = `<span>${lang}</span> <span>${count} files</span>`;
    langContainer.appendChild(item);
  });

  const manContainer = document.getElementById("autopsyManifestsList");
  manContainer.innerHTML = "";
  (scan.manifests || []).forEach(m => {
    const item = document.createElement("div");
    item.className = "sub-item";
    item.innerHTML = `<span>${m.file}</span> <span style="color:var(--spectral-cyan);">${m.ecosystem}</span>`;
    manContainer.appendChild(item);
  });

  // Verified Facts vs Hypotheses
  const tableBody = document.getElementById("autopsyFactsTableBody");
  tableBody.innerHTML = "";

  (autopsy.verified_facts || []).forEach(vf => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="fact-badge verified">Verified Fact</span></td>
      <td>${escapeHtml(vf.description)}</td>
      <td><code class="citation-tag">${escapeHtml(vf.citation || "")}</code></td>
    `;
    tableBody.appendChild(tr);
  });

  (autopsy.hypotheses || []).forEach(hp => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="fact-badge hypothesis">Hypothesis</span></td>
      <td>${escapeHtml(hp.claim)}</td>
      <td><span class="text-dim">${escapeHtml(hp.reason || "Requires human verification")}</span></td>
    `;
    tableBody.appendChild(tr);
  });

  // TODOs
  const todoContainer = document.getElementById("autopsyTodoList");
  todoContainer.innerHTML = "";
  if (!scan.todos || scan.todos.length === 0) {
    todoContainer.innerHTML = `<div class="text-muted">No unresolved TODOs or FIXMEs found.</div>`;
  } else {
    scan.todos.forEach(t => {
      const item = document.createElement("div");
      item.className = "todo-item";
      item.innerHTML = `
        <div><span class="todo-tag">${t.tag}</span> <span>${escapeHtml(t.text)}</span></div>
        <div class="todo-file">${t.file}:L${t.line}</div>
      `;
      todoContainer.appendChild(item);
    });
  }

  // Load roadmap tasks
  loadRoadmapTasks(currentProjectId);
}

/* ==========================================================================
   Ghost Chat
   ========================================================================== */
function initChatListeners() {
  const sendBtn = document.getElementById("sendChatBtn");
  const chatInput = document.getElementById("chatInput");

  sendBtn.addEventListener("click", () => sendGhostMessage());
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendGhostMessage();
  });

  document.querySelectorAll(".prompt-chips .chip-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      chatInput.value = btn.dataset.prompt;
      sendGhostMessage();
    });
  });
}

async function sendGhostMessage() {
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  if (!query) return;

  if (!currentProjectId) {
    alert("Please initiate a séance on a repository first!");
    switchTab("seance");
    return;
  }

  appendChatMessage("user", query);
  input.value = "";

  // Append thinking ghost bubble
  const thinkingId = appendChatMessage("ghost", "Consulting repository archives...", true);

  try {
    const res = await fetch(`${API_BASE}/api/projects/${currentProjectId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: query })
    });

    if (!res.ok) throw new Error("Ghost Chat failed to retrieve answers.");
    const data = await res.json();

    removeChatMessage(thinkingId);
    appendChatMessage("ghost", data.answer, false, data.evidence);

  } catch (err) {
    removeChatMessage(thinkingId);
    appendChatMessage("ghost", `The séance encountered a disturbance: ${err.message}`);
  }
}

function appendChatMessage(role, text, isThinking = false, evidence = []) {
  const container = document.getElementById("chatMessages");
  const msgEl = document.createElement("div");
  const msgId = "msg-" + Date.now();
  msgEl.id = msgId;
  msgEl.className = `msg ${role === "user" ? "user-msg" : "ghost-msg"}`;

  let inner = `
    <div class="msg-avatar">${role === "user" ? "👤" : "👻"}</div>
    <div class="msg-bubble">
      <p>${escapeHtml(text)}</p>
  `;

  if (evidence && evidence.length > 0) {
    inner += `<div class="evidence-list" style="margin-top:0.75rem;">`;
    evidence.forEach(c => {
      inner += `
        <div class="evidence-card">
          <div class="evidence-header">
            <span>📄 ${c.file}</span>
            <span>Lines ${c.start_line}-${c.end_line}</span>
          </div>
          <div class="evidence-content">${escapeHtml(c.content)}</div>
        </div>
      `;
    });
    inner += `</div>`;
  }

  inner += `</div>`;
  msgEl.innerHTML = inner;
  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
  return msgId;
}

function removeChatMessage(msgId) {
  const el = document.getElementById(msgId);
  if (el) el.remove();
}

/* ==========================================================================
   Revival Roadmap
   ========================================================================== */
function initRoadmapListeners() {
  const exportBtn = document.getElementById("exportDossierBtn");
  const topExportBtn = document.getElementById("exportDossierTopBtn");

  const exportHandler = () => {
    if (!currentProjectId) {
      alert("No active séance to export.");
      return;
    }
    window.open(`${API_BASE}/api/projects/${currentProjectId}/report`, "_blank");
  };

  if (exportBtn) exportBtn.addEventListener("click", exportHandler);
  if (topExportBtn) topExportBtn.addEventListener("click", exportHandler);
}

async function loadRoadmapTasks(projectId) {
  try {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/tasks`);
    if (!res.ok) return;
    const tasks = await res.json();
    renderRoadmapGrid(tasks);
  } catch (err) {
    console.error("Failed to load tasks", err);
  }
}

function renderRoadmapGrid(tasks) {
  const grid = document.getElementById("roadmapGrid");
  grid.innerHTML = "";

  const categories = [
    { key: "Investigate First", icon: "🚨" },
    { key: "Dependency Modernization", icon: "📦" },
    { key: "Missing Tests", icon: "🧪" },
    { key: "Documentation Patches", icon: "📝" }
  ];

  categories.forEach(cat => {
    const col = document.createElement("div");
    col.className = "roadmap-col";

    const catTasks = tasks.filter(t => t.category === cat.key || (cat.key === "Investigate First" && !["Dependency Modernization", "Missing Tests", "Documentation Patches"].includes(t.category)));

    col.innerHTML = `
      <div class="col-header">
        <span>${cat.icon} ${cat.key}</span>
        <span class="badge" style="background:rgba(255,255,255,0.06); font-size:0.75rem;">${catTasks.length}</span>
      </div>
      <div class="task-list"></div>
    `;

    const list = col.querySelector(".task-list");
    catTasks.forEach(task => {
      const card = document.createElement("div");
      card.className = "task-card";
      card.innerHTML = `
        <div class="task-title">${escapeHtml(task.title)}</div>
        <div class="task-desc">${escapeHtml(task.description)}</div>
        <div class="task-meta">
          <span class="priority-tag ${task.priority}">${task.priority}</span>
          <select class="status-select" data-task-id="${task.id}">
            <option value="Pending" ${task.status === "Pending" ? "selected" : ""}>Pending</option>
            <option value="In Progress" ${task.status === "In Progress" ? "selected" : ""}>In Progress</option>
            <option value="Completed" ${task.status === "Completed" ? "selected" : ""}>Completed</option>
          </select>
        </div>
      `;

      card.querySelector(".status-select").addEventListener("change", (e) => {
        updateTaskState(task.id, e.target.value);
      });

      list.appendChild(card);
    });

    grid.appendChild(col);
  });
}

async function updateTaskState(taskId, newStatus) {
  try {
    await fetch(`${API_BASE}/api/projects/${currentProjectId}/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
  } catch (err) {
    console.error("Failed to update task", err);
  }
}

/* ==========================================================================
   Recent Projects
   ========================================================================== */
async function loadRecentProjects() {
  const container = document.getElementById("projectsList");
  try {
    const res = await fetch(`${API_BASE}/api/projects`);
    if (!res.ok) return;
    const projects = await res.json();
    if (!projects || projects.length === 0) {
      container.innerHTML = `<div class="empty-state">No archived repositories yet. Summon your first codebase above!</div>`;
      return;
    }

    container.innerHTML = "";
    projects.forEach(p => {
      const item = document.createElement("div");
      item.className = "project-item";
      item.innerHTML = `
        <div class="p-item-name">👻 ${escapeHtml(p.name)}</div>
        <div class="p-item-meta">${p.total_files} files • ${p.commit_count} commits</div>
      `;
      item.addEventListener("click", async () => {
        const fullRes = await fetch(`${API_BASE}/api/projects/${p.id}`);
        if (fullRes.ok) {
          const fullData = await fullRes.json();
          currentProjectId = p.id;
          currentProjectData = {
            project_id: p.id,
            name: fullData.name,
            path: fullData.source_path,
            scan: fullData.analysis?.scan || {},
            autopsy: fullData.analysis?.autopsy || {}
          };
          renderAutopsy(currentProjectData);
          switchTab("autopsy");
        }
      });
      container.appendChild(item);
    });
  } catch (err) {
    console.error("Failed to fetch projects", err);
  }
}

/* ==========================================================================
   Settings
   ========================================================================== */
function initSettingsListeners() {
  const saveBtn = document.getElementById("saveSettingsBtn");
  const testBtn = document.getElementById("testOllamaBtn");
  const urlInput = document.getElementById("settingOllamaUrl");
  const modelSelect = document.getElementById("settingModelSelect");
  const statusEl = document.getElementById("settingsSaveStatus");

  saveBtn.addEventListener("click", async () => {
    try {
      const res = await fetch(`${API_BASE}/api/models/configure`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: urlInput.value.trim(),
          model_name: modelSelect.value
        })
      });
      if (res.ok) {
        statusEl.innerText = "✓ Settings applied successfully!";
        checkOllamaStatus();
      }
    } catch (err) {
      statusEl.innerText = "Error applying settings.";
    }
  });

  testBtn.addEventListener("click", async () => {
    checkOllamaStatus();
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
