const CASE_KEY = "agrinexus_compliance_case_id";

const STATUS_LABELS = {
  APPLY_OK: "OK to apply as planned",
  WEATHER_BLOCK: "Do not apply: weather exceeds label limits",
  POINTS_SHORT: "Do not apply: more mitigation is required",
  PLANNED: "Plan ready — awaiting confirmation",
  NUDGED: "Reminder sent — awaiting confirmation",
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

function formatSprayDate(isoDate) {
  if (!isoDate) return "date not set";
  try {
    const d = new Date(isoDate + "T12:00:00");
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(d);
  } catch {
    return isoDate;
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

/**
 * Wire applicator flow stepper: 1 Plan → 2 Confirm → 3 Receipt.
 * Steps 2–3 look unreachable until a case exists (unless current).
 */
function wireApplicatorStepper(current) {
  const caseId = getCaseId();
  const hasCase = !!caseId;
  document.querySelectorAll("[data-stepper] .stepper-item").forEach((el) => {
    const step = el.getAttribute("data-step");
    const link = el.querySelector("a");
    el.classList.toggle("is-current", step === current);
    el.classList.toggle("is-done", stepOrder(step) < stepOrder(current) && hasCase);
    if (!link) return;
    if (step === "plan") {
      link.href = "/check.html";
      link.removeAttribute("aria-disabled");
      el.classList.remove("is-locked");
    } else if (step === "confirm") {
      if (hasCase) {
        link.href = "/confirm.html?case_id=" + encodeURIComponent(caseId);
        link.removeAttribute("aria-disabled");
        el.classList.remove("is-locked");
      } else {
        link.href = "#";
        link.setAttribute("aria-disabled", "true");
        el.classList.add("is-locked");
      }
    } else if (step === "receipt") {
      if (hasCase) {
        link.href = "/receipt.html?case_id=" + encodeURIComponent(caseId);
        link.removeAttribute("aria-disabled");
        el.classList.remove("is-locked");
      } else {
        link.href = "#";
        link.setAttribute("aria-disabled", "true");
        el.classList.add("is-locked");
      }
    }
  });
}

function stepOrder(step) {
  if (step === "plan") return 1;
  if (step === "confirm") return 2;
  if (step === "receipt") return 3;
  return 0;
}

function buildPlanSummarySentence(plan, sprayDate) {
  const field = plan.field || {};
  const product = plan.product || {};
  const pts = plan.points || {};
  const wx = plan.weather || {};
  const actions = plan.bulletin_actions || [];
  const place = [field.county, field.state].filter(Boolean).join(", ") || "Field";
  const productName = product.product_name || product.epa_reg_no || "product";
  const dateBit = formatSprayDate(sprayDate);
  const req = pts.required_points ?? "—";
  const earned = pts.earned_points ?? "—";
  let outcome = statusLabel(plan.status);
  if (plan.status === "APPLY_OK") {
    outcome = `your practices earn ${earned} — OK to apply`;
  } else if (plan.status === "POINTS_SHORT") {
    outcome = `your practices earn ${earned} — short by ${pts.shortfall} (do not apply yet)`;
  } else if (plan.status === "WEATHER_BLOCK") {
    outcome = `your practices earn ${earned}, but weather blocks application`;
  }
  const windBit = wx.weather_ok
    ? "Wind forecast within limits."
    : `Wind ${wx.wind_mph ?? "—"} mph exceeds label limits.`;
  const n = actions.length;
  const bulletinBit =
    n === 0
      ? "No extra bulletin actions listed."
      : `${n} bulletin action${n === 1 ? "" : "s"} required before application.`;
  return `${place} · ${productName} · planned spray ${dateBit}. ${req} mitigation points required, ${outcome}. ${windBit} ${bulletinBit}`;
}
