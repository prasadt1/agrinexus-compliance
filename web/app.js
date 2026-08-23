const CASE_KEY = "agrinexus_compliance_case_id";

function getCaseId() {
  return localStorage.getItem(CASE_KEY) || "";
}

function setCaseId(id) {
  localStorage.setItem(CASE_KEY, id);
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
