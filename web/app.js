const CASE_KEY = "agrinexus_compliance_case_id";

const STATUS_LABELS = {
  APPLY_OK: "OK to apply as planned",
  WEATHER_BLOCK: "Do not apply: weather exceeds label limits",
  POINTS_SHORT: "Do not apply: more mitigation is required",
  LABEL_DATE_BLOCK: "Do not apply: label date cutoff",
  BULLETIN_MONTH_BLOCK: "Do not apply: bulletin month does not match",
  PLANNED: "Planned",
  NUDGED: "Reminded",
  CONFIRMED: "Awaiting verdict",
  VERIFIED: "Verified",
  NEEDS_REVIEW: "Needs review",
  EXPIRED: "Expired",
  CLOSED: "Closed",
  BLOCKED: "Blocked",
};

const EVENT_LABELS = {
  planned: "Plan created",
  reminder_simulated: "Reminder sent",
  reminder_sent: "Reminder sent",
  confirm_needs_human: "Confirmation needs human review",
  confirmed: "Confirmation recorded",
  expired: "No reply, expired",
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

function statusLabel(code, outcome) {
  if (!code) return "—";
  if (code === "CLOSED" && outcome) {
    return `Closed (${outcome})`;
  }
  return STATUS_LABELS[code] || String(code).replace(/_/g, " ");
}

function eventLabel(ev) {
  if (!ev) return "—";
  if (ev.type === "reminder_simulated" || ev.type === "reminder_sent") {
    const data = ev.data || {};
    const byPartner =
      ev.actor === "partner" || data.sent_by === "partner";
    const base = byPartner
      ? "Reminder sent by partner"
      : "Reminder sent on schedule";
    if (ev.which) return `${base} (${ev.which})`;
    if (data.nudge_count) return `${base} (#${data.nudge_count})`;
    return base;
  }
  const base = EVENT_LABELS[ev.type] || ev.type;
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
  const place = [field.county, field.state].filter(Boolean).join(", ") || "Field";
  const productName = product.product_name || product.epa_reg_no || "product";
  const dateBit = formatSprayDate(sprayDate);
  const req = pts.required_points ?? "—";
  const earned = pts.earned_points ?? "—";
  const shortfall = pts.shortfall;
  const lead = `${place} · ${productName} · planned spray ${dateBit}.`;

  if (plan.status === "APPLY_OK") {
    return (
      `${lead} ${req} mitigation points required; your practices earn ${earned} — OK to apply. ` +
      `Wind forecast within limits.`
    );
  }
  if (plan.status === "LABEL_DATE_BLOCK") {
    const cut = plan.label_date_cutoff || {};
    const msg =
      cut.message ||
      "The label date cutoff blocks application.";
    return (
      `${lead} ${msg} Separately, ${req} mitigation points are required and your practices earn ${earned}` +
      (shortfall != null ? ` (short by ${shortfall})` : "") +
      `. Wind forecast ${wx.weather_ok ? "within limits" : "also exceeds limits"}.`
    );
  }
  if (plan.status === "BULLETIN_MONTH_BLOCK") {
    const gate = plan.bulletin_month_gate || {};
    return (
      `${lead} ${gate.message || "The bulletin month does not match the planned date."} ` +
      `${req} mitigation points would be required; your practices earn ${earned}.`
    );
  }
  if (plan.status === "POINTS_SHORT") {
    return (
      `${lead} ${req} mitigation points required; your practices earn ${earned} — short by ${shortfall} (do not apply yet). ` +
      `Wind forecast within limits.`
    );
  }
  if (plan.status === "WEATHER_BLOCK") {
    return (
      `${lead} ${req} mitigation points required; your practices earn ${earned}, but weather blocks application. ` +
      `Wind ${wx.wind_mph ?? "—"} mph exceeds label limits.`
    );
  }
  return `${lead} ${statusLabel(plan.status)}.`;
}

function formatBulletinPrinted(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso.includes("T") ? iso : iso + "T12:00:00");
    return new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(d);
  } catch {
    return iso;
  }
}

function packFooterText(plan) {
  const field = (plan && plan.field) || {};
  const product = (plan && plan.product) || {};
  const place = [field.county, field.state].filter(Boolean).join(", ");
  const pname = product.product_name || "sample pack";
  const reg = product.epa_reg_no || "";
  return (
    `Sample educational data · ${place || "Field"} · ${pname}` +
    (reg ? ` (${reg})` : "")
  );
}

/** Full-page screenshot mode: sticky header renders once (no stitch artifact). */
(function applyCaptureMode() {
  try {
    if (new URLSearchParams(location.search).get("capture") !== "1") return;
    document.documentElement.classList.add("capture-mode");
    const style = document.createElement("style");
    style.textContent =
      "html.capture-mode .top, html.capture-mode .site-header, " +
      "html.capture-mode header.site-header, html.capture-mode .topbar, " +
      "html.capture-mode .app-header { position: static !important; }";
    document.head.appendChild(style);
  } catch {
    /* ignore */
  }
})();

/** Persistent demo honesty banner on every page. */
(function injectDemoBanner() {
  if (document.querySelector(".demo-banner")) return;
  const p = document.createElement("p");
  p.className = "demo-banner";
  p.setAttribute("role", "note");
  p.textContent =
    "Demonstration with sample data. No live applicators, no live text messages. Educational, not legal advice.";
  document.body.insertBefore(p, document.body.firstChild);
})();
