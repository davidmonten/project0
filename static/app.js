const state = { jobId: null, items: [] };

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function ensureJob() {
  if (state.jobId) return state.jobId;
  const data = await api("/api/jobs", { method: "POST" });
  state.jobId = data.job_id;
  return state.jobId;
}

// ---- Page preset ----
const PRESETS = {
  "100x150": { w: 100, h: 150, mode: "sheet" },
  a4: { w: 210, h: 297, mode: "sheet" },
  roll100: { w: 100, h: 150, mode: "roll" },
};

$("page-preset").addEventListener("change", (e) => {
  const preset = PRESETS[e.target.value];
  if (!preset) return;
  $("page-w").value = preset.w;
  $("page-h").value = preset.h;
  $("page-mode").value = preset.mode;
});

// ---- Upload ----
const dropzone = $("dropzone");
["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
$("file-input").addEventListener("change", (e) => uploadFiles(e.target.files));

async function uploadFiles(fileList) {
  if (!fileList || fileList.length === 0) return;
  await ensureJob();
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  const data = await api(`/api/jobs/${state.jobId}/items`, { method: "POST", body: form });
  state.items = data.items;
  renderItems();
}

function renderItems() {
  const table = $("items-table");
  const tbody = table.querySelector("tbody");
  tbody.innerHTML = "";
  table.hidden = state.items.length === 0;
  for (const item of state.items) {
    const tr = document.createElement("tr");
    const size = item.detected_width_mm
      ? `${item.detected_width_mm.toFixed(1)} x ${item.detected_height_mm.toFixed(1)} mm`
      : "-";
    tr.innerHTML = `
      <td>${item.filename}</td>
      <td>${item.kind}</td>
      <td>${item.page_count}</td>
      <td>${size} ${item.detected_width_mm ? '<button class="use-size" title="Usa come dimensione carta">usa</button>' : ""}</td>
      <td><input type="number" min="1" value="${item.copies}" data-id="${item.id}" class="copies-input" /></td>
      <td><button class="remove" data-id="${item.id}">&times;</button></td>
    `;
    if (item.detected_width_mm) {
      tr.querySelector(".use-size").addEventListener("click", () => {
        $("card-w").value = item.detected_width_mm.toFixed(1);
        $("card-h").value = item.detected_height_mm.toFixed(1);
      });
    }
    tr.querySelector(".copies-input").addEventListener("change", async (e) => {
      const copies = parseInt(e.target.value, 10) || 1;
      await api(`/api/jobs/${state.jobId}/items/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ copies }),
      });
      item.copies = copies;
    });
    tr.querySelector(".remove").addEventListener("click", async () => {
      const data = await api(`/api/jobs/${state.jobId}/items/${item.id}`, { method: "DELETE" });
      state.items = data.items;
      renderItems();
    });
    tbody.appendChild(tr);
  }
}

// ---- Layout preview ----
$("btn-preview").addEventListener("click", async () => {
  if (!state.jobId || state.items.length === 0) {
    alert("Carica almeno un file prima.");
    return;
  }
  const payload = {
    page: {
      width_mm: parseFloat($("page-w").value),
      height_mm: parseFloat($("page-h").value),
      mode: $("page-mode").value,
    },
    card: {
      width_mm: parseFloat($("card-w").value),
      height_mm: parseFloat($("card-h").value),
    },
    opts: {
      margin_mm: parseFloat($("margin").value),
      gutter_mm: parseFloat($("gutter").value),
      allow_rotation: $("allow-rotation").checked,
    },
  };
  try {
    const data = await api(`/api/jobs/${state.jobId}/layout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderLayout(data);
  } catch (err) {
    alert(`Errore: ${err.message}`);
  }
});

function renderLayout(data) {
  const { layout, output_pdf_url, preview_urls } = data;
  $("layout-stats").textContent =
    `${layout.cols} x ${layout.rows} carte per pagina` +
    (layout.rotated ? " (ruotate 90°)" : "") +
    ` — ${layout.pages.length} pagina/e, ${layout.total_cards} carte totali, ` +
    `${layout.wasted_area_pct}% area non utilizzata`;

  const previews = $("previews");
  previews.innerHTML = "";
  for (const url of preview_urls) {
    const img = document.createElement("img");
    img.src = url + `?t=${Date.now()}`;
    previews.appendChild(img);
  }

  const link = $("download-link");
  link.href = output_pdf_url;
  link.hidden = false;

  $("btn-print").disabled = false;
}

// ---- Printer config ----
async function loadPrinterConfig() {
  const cfg = await api("/api/printer/config");
  $("cfg-cli").value = cfg.cli_path || "";
  $("cfg-name").value = cfg.printer_name || "";
  $("cfg-model").value = cfg.printer_model || "d100";
}

$("btn-save-config").addEventListener("click", async () => {
  await api("/api/printer/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cli_path: $("cfg-cli").value,
      printer_name: $("cfg-name").value,
      printer_model: $("cfg-model").value,
    }),
  });
  $("config-status").textContent = "Configurazione salvata.";
});

$("btn-print").addEventListener("click", async () => {
  $("print-status").textContent = "Stampa in corso...";
  try {
    const res = await fetch(`/api/jobs/${state.jobId}/print`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      $("print-status").textContent = "Stampa inviata con successo.";
    } else {
      $("print-status").textContent = `Errore: ${data.error || data.stderr || "sconosciuto"}`;
    }
  } catch (err) {
    $("print-status").textContent = `Errore: ${err.message}`;
  }
});

loadPrinterConfig();
ensureJob();
