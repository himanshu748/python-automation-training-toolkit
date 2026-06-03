const $ = (id) => document.getElementById(id);
const API_BASE = window.location.port === "3000" ? "http://127.0.0.1:8000" : "";

const owners = {
  email: "Training",
  location: "Utility",
  ec2: "Cloud",
  s3: "Cloud",
  search_summary: "Models",
  image_detection: "Models",
  hand_gestures: "Gestures",
};

function labelize(name) {
  return name
    .replaceAll("_", " ")
    .replace(/\b\w/g, (x) => x.toUpperCase())
    .replace("Ec2", "EC2")
    .replace("S3", "S3");
}

function json(value) {
  return JSON.stringify(value, null, 2);
}

function formatResult(payload, kind = "default") {
  if (!payload.ok) {
    return `Status: failed\n\n${payload.error}`;
  }

  const result = payload.result;
  if (kind === "location") {
    const coords = Array.isArray(result.coordinates)
      ? result.coordinates.filter((item) => item !== null && item !== undefined).join(", ")
      : "Unavailable";
    const addressLines = result.address && Object.keys(result.address).length
      ? Object.entries(result.address).map(([key, value]) => `  ${key}: ${value}`).join("\n")
      : "  No address details returned";
    return [
      "Status: success",
      "",
      `Location: ${result.display || "Detected"}`,
      `City: ${result.city || "Unavailable"}`,
      `Region: ${result.region || "Unavailable"}`,
      `Country: ${result.country || "Unavailable"}`,
      `Coordinates: ${coords}`,
      `IP: ${result.ip || "Unavailable"}`,
      `Source: ${result.source || "Unknown"}`,
      "",
      "Address Details:",
      addressLines,
    ].join("\n");
  }

  if (kind === "text") {
    return `Status: success\n\n${result}`;
  }

  if (typeof result === "string") {
    return `Status: success\n\n${result}`;
  }

  return `Status: success\n\n${json(result)}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Request failed");
  return payload;
}

function log(title, detail, tone = "slate") {
  const container = $("activity-log");
  if (!container) return;
  const palette = {
    slate: "bg-slate-50 text-slate-600 border-slate-200",
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    red: "bg-rose-50 text-rose-700 border-rose-200",
  };
  const row = document.createElement("div");
  row.className = "p-4";
  row.innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-sm font-semibold text-slate-950">${title}</p>
        <p class="mt-1 text-xs leading-5 text-slate-500">${detail}</p>
      </div>
      <span class="shrink-0 rounded-md border px-2 py-1 text-[11px] font-medium ${palette[tone]}">${new Date().toLocaleTimeString()}</span>
    </div>`;
  container.prepend(row);
}

function updateEnvironment(config) {
  const target = $("sidebar-env");
  if (!target) return;
  target.innerHTML = `
    <div class="flex justify-between gap-3"><span class="text-slate-500">HF Token</span><span>${config.hf_token}</span></div>
    <div class="flex justify-between gap-3"><span class="text-slate-500">AWS Region</span><span>${config.aws_region}</span></div>
    <div class="flex justify-between gap-3"><span class="text-slate-500">S3 Bucket</span><span class="truncate">${config.s3_bucket}</span></div>`;
}

function renderOverview(payload) {
  const overview = $("overview-kpis");
  const table = $("readiness-table");
  if (!overview && !table) return;

  const config = payload.configuration;
  const entries = Object.entries(payload.features);
  const ready = entries.filter(([, item]) => item.ready).length;
  const readyCount = $("ready-count");
  if (readyCount) readyCount.textContent = `${ready}/${entries.length} ready`;

  if (overview) {
    const kpis = [
      ["System Health", `${ready}/${entries.length}`, "configured workflows", ready === entries.length ? "emerald" : "amber"],
      ["HF Token", config.hf_token, config.hf_text_model.split("/").pop(), config.hf_token === "set" ? "emerald" : "rose"],
      ["AWS Region", config.aws_region, "cloud workflow target", config.aws_region === "missing" ? "rose" : "blue"],
      ["Utilities", "ready", "safe helper actions", "violet"],
    ];
    const color = {
      emerald: "bg-emerald-50",
      amber: "bg-amber-50",
      rose: "bg-rose-50",
      blue: "bg-blue-50",
      violet: "bg-violet-50",
    };
    overview.innerHTML = kpis.map(([title, value, sub, tone]) => `
      <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-panel">
        <div class="flex items-center justify-between">
          <p class="text-xs font-medium uppercase tracking-wide text-slate-500">${title}</p>
          <span class="size-2.5 rounded-full ${color[tone]}"></span>
        </div>
        <p class="mt-4 truncate text-2xl font-semibold tracking-tight text-slate-950">${value}</p>
        <p class="mt-1 truncate text-sm text-slate-500">${sub}</p>
      </div>`).join("");
  }

  if (table) {
    table.innerHTML = entries.map(([name, details]) => {
      const missing = [...details.missing_config, ...details.missing_dependencies];
      return `
        <tr>
          <td class="px-4 py-3 font-medium text-slate-900">${labelize(name)}</td>
          <td class="px-4 py-3">
            <span class="rounded-md px-2 py-1 text-xs font-medium ${details.ready ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"}">${details.ready ? "Ready" : "Needs setup"}</span>
          </td>
          <td class="max-w-[420px] px-4 py-3 text-slate-500">${missing.length ? missing.join(", ") : "None"}</td>
          <td class="px-4 py-3 text-slate-500">${owners[name] || "Core"}</td>
        </tr>`;
    }).join("");
  }
}

async function refreshHealth() {
  const payload = await api("/api/health");
  updateEnvironment(payload.configuration);
  renderOverview(payload);
  log("Health refreshed", "System readiness and safe configuration updated.", "green");
}

function bind(id, eventName, handler) {
  const element = $(id);
  if (element) element.addEventListener(eventName, handler);
}

async function runOutputAction(outputId, loadingMessage, action, kind = "default") {
  const output = $(outputId);
  if (!output) return;
  output.textContent = loadingMessage;
  try {
    const payload = await action();
    output.textContent = formatResult(payload, kind);
  } catch (error) {
    const message = error && error.message ? error.message : "Request failed";
    output.textContent = `Status: failed\n\n${message}`;
    log("Workflow failed", message, "red");
  }
}

function bindOverviewPage() {
  bind("refresh-btn", "click", () => refreshHealth().catch((error) => log("Refresh failed", error.message, "red")));
  bind("clear-log", "click", () => {
    const target = $("activity-log");
    if (target) target.innerHTML = "";
  });
}

function bindModelPage() {
  bind("summary-btn", "click", () => runOutputAction(
    "summary-output",
    "Generating summary...",
    () => api("/api/search-summary", {
      method: "POST",
      body: JSON.stringify({ query: $("summary-query").value }),
    }),
    "text",
  ));
  bind("image-btn", "click", () => runOutputAction(
    "summary-output",
    "Captioning image...",
    () => api("/api/describe-image", {
      method: "POST",
      body: JSON.stringify({ image_path: $("image-path").value }),
    }),
    "text",
  ));
}

function bindCloudPage() {
  bind("ec2-btn", "click", () => runOutputAction(
    "cloud-output",
    "Loading EC2 instances...",
    () => api("/api/list-ec2"),
  ));
  bind("ec2-launch-btn", "click", () => runOutputAction(
    "cloud-output",
    "Launching EC2 instance...",
    () => api("/api/launch-ec2", { method: "POST", body: "{}" }),
  ));
  bind("ec2-stop-btn", "click", () => runOutputAction(
    "cloud-output",
    "Stopping EC2 instance...",
    () => api("/api/stop-ec2", {
      method: "POST",
      body: JSON.stringify({ instance_id: $("instance-id").value }),
    }),
  ));
  bind("s3-btn", "click", () => runOutputAction(
    "cloud-output",
    "Loading S3 objects...",
    () => {
      const prefix = encodeURIComponent($("s3-prefix").value);
      const limit = encodeURIComponent($("s3-limit").value || "10");
      return api(`/api/list-s3?prefix=${prefix}&limit=${limit}`);
    },
  ));
  bind("s3-upload-btn", "click", () => runOutputAction(
    "cloud-output",
    "Uploading S3 object...",
    () => api("/api/upload-s3", {
      method: "POST",
      body: JSON.stringify({ file_path: $("local-file-path").value, key: $("s3-key").value }),
    }),
  ));
  bind("s3-download-btn", "click", () => runOutputAction(
    "cloud-output",
    "Downloading S3 object...",
    () => api("/api/download-s3", {
      method: "POST",
      body: JSON.stringify({ key: $("s3-key").value, destination: $("download-destination").value }),
    }),
  ));
  bind("s3-delete-btn", "click", () => runOutputAction(
    "cloud-output",
    "Deleting S3 object...",
    () => api("/api/delete-s3", {
      method: "POST",
      body: JSON.stringify({ key: $("s3-key").value }),
    }),
  ));
}

function bindUtilityPage() {
  bind("location-btn", "click", () => runOutputAction(
    "utility-output",
    "Looking up location...",
    () => api("/api/location"),
    "location",
  ));
}

document.addEventListener("DOMContentLoaded", () => {
  bindOverviewPage();
  bindModelPage();
  bindCloudPage();
  bindUtilityPage();
  refreshHealth().catch((error) => log("Health refresh failed", error.message, "red"));
});
