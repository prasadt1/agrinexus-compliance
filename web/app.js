const CASE_KEY = "agrinexus_compliance_case_id";

const STATUS_LABELS = {
  APPLY_OK: "Application conditions met",
  WEATHER_BLOCK: "Do not apply yet: weather exceeds label limits",
  POINTS_SHORT: "More mitigation is required",
  PLANNED: "Plan ready — awaiting confirmation",
  NUDGED: "Waiting for applicator confirmation",
  CONFIRMED: "Application record completed",
  EXPIRED: "Case expired",
  BLOCKED: "Application blocked",
};

const EVENT_LABELS = {
  planned: "Plan created",
  reminder_simulated: "Reminder sent",
  confirm_needs_human: "Confirmation needs human review",
  confirmed: "Confirmation recorded",
};

function getCaseId() {
  return localStorage.getItem(CASE_KEY) || "";
}

function setCaseId(id) {
  localStorage.setItem(CASE_KEY, id);
}

function clearCaseId() {
  localStorage.removeItem(CASE_KEY);
}

function resolveCaseId() {
  const fromUrl = new URLSearchParams(location.search).get("case_id");
  if (fromUrl) {
    setCaseId(fromUrl);
    return fromUrl;
  }
  return getCaseId();
}

function statusLabel(code) {
  if (!code) return "—";
  return STATUS_LABELS[code] || String(code).replace(/_/g, " ");
}

function eventLabel(ev) {
  if (!ev) return "—";
  const base = EVENT_LABELS[ev.type] || ev.type;
  if (ev.type === "reminder_simulated" && ev.which) {
    return `${base} (${ev.which})`;
  }
  return base;
}

function formatWhen(iso) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function practiceNames(credited) {
  if (!Array.isArray(credited) || !credited.length) return [];
  return credited.map((c) => c.name || c.id);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText || "request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function setBusy(button, busy, idleLabel) {
  if (!button) return;
  if (busy) {
    button.dataset.idleLabel = button.dataset.idleLabel || button.textContent;
    button.disabled = true;
    button.textContent = button.dataset.busyLabel || "Working…";
  } else {
    button.disabled = false;
    button.textContent = idleLabel || button.dataset.idleLabel || button.textContent;
  }
}

function showError(el, message) {
  if (!el) return;
  el.hidden = !message;
  el.textContent = message || "";
}

function renderTimeline(container, events) {
  if (!container) return;
  container.innerHTML = "";
  if (!events || !events.length) {
    const li = document.createElement("li");
    li.className = "timeline-empty";
    li.textContent = "No activity yet.";
    container.appendChild(li);
    return;
  }
  events.forEach((ev) => {
    const li = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = eventLabel(ev);
    const meta = document.createElement("span");
    meta.className = "timeline-meta";
    meta.textContent = formatWhen(ev.at);
    const detail = document.createElement("p");
    detail.textContent = ev.detail || "";
    li.appendChild(title);
    li.appendChild(meta);
    if (ev.detail) li.appendChild(detail);
    container.appendChild(li);
  });
}
