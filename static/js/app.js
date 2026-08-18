/**
 * Vanilla-JS single page app: hash-based router with three views
 * (Tables list, New Table form, Table Data grid).
 */

const app = document.getElementById("app");

const TYPE_LABELS = {
  text: "Text",
  integer: "Whole Number (Integer)",
  number: "Decimal Number",
};

const NUMERIC_TYPES = new Set(["integer", "number"]);

const APP_TITLE = "Reference Data Management";

function setPageTitle(subtitle) {
  document.title = subtitle ? `${APP_TITLE} - ${subtitle}` : APP_TITLE;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 204) {
    return null;
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((data && data.error) || `Request failed (${response.status})`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

function parseRoute() {
  const hash = window.location.hash.replace(/^#/, "") || "/tables";
  const parts = hash.split("/").filter(Boolean);

  if (parts[0] === "tables" && parts[1] === "new") {
    return { view: "new-table" };
  }
  if (parts[0] === "tables" && parts[1]) {
    return { view: "table-data", slug: decodeURIComponent(parts[1]) };
  }
  return { view: "tables" };
}

function render() {
  const route = parseRoute();
  if (route.view === "tables") {
    renderTablesView();
  } else if (route.view === "new-table") {
    renderNewTableView();
  } else if (route.view === "table-data") {
    renderTableDataView(route.slug);
  }
}

window.addEventListener("hashchange", render);
window.addEventListener("DOMContentLoaded", render);

// ---------------------------------------------------------------------------
// Tables list view
// ---------------------------------------------------------------------------

async function renderTablesView() {
  setPageTitle("Tables");
  app.innerHTML = `
    <section class="view">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h3 mb-0">Tables</h1>
        <a class="btn btn-primary" href="#/tables/new">+ Add Table</a>
      </div>
      <ul class="list-group" id="table-list"><li class="list-group-item text-muted">Loading&hellip;</li></ul>
    </section>
  `;

  const listEl = document.getElementById("table-list");
  try {
    const tables = await api("/api/tables");
    if (tables.length === 0) {
      listEl.innerHTML = `<li class="list-group-item text-muted">No tables yet. Add one to get started.</li>`;
      return;
    }
    listEl.innerHTML = tables
      .map(
        (table) => `
          <li class="list-group-item p-0">
            <a class="list-group-item list-group-item-action border-0" href="#/tables/${encodeURIComponent(table.slug)}">${escapeHtml(table.name)}</a>
          </li>
        `
      )
      .join("");
  } catch (err) {
    listEl.innerHTML = `<li class="list-group-item text-danger">${escapeHtml(err.message)}</li>`;
  }
}

// ---------------------------------------------------------------------------
// New Table view
// ---------------------------------------------------------------------------

function renderNewTableView() {
  setPageTitle("New Table");
  app.innerHTML = `
    <section class="view">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h3 mb-0">New Table</h1>
        <a class="btn btn-outline-secondary" href="#/tables">Cancel</a>
      </div>
      <div class="alert alert-danger" id="form-error" hidden></div>
      <form id="new-table-form" class="card p-3">
        <div class="mb-3">
          <label class="form-label" for="table-name">Table name</label>
          <input type="text" class="form-control" id="table-name" required />
        </div>

        <div id="fields-container"></div>

        <button type="button" class="btn btn-outline-secondary mb-3" id="add-field-btn">+ Add field</button>

        <div class="form-actions d-flex gap-2">
          <button type="submit" class="btn btn-primary">Save</button>
        </div>
      </form>
    </section>
  `;

  const fieldsContainer = document.getElementById("fields-container");
  const errorEl = document.getElementById("form-error");

  function addFieldRow() {
    const row = document.createElement("div");
    row.className = "field-row row g-2 mb-2 align-items-center";
    row.innerHTML = `
      <div class="col"><input type="text" class="field-name form-control" placeholder="Field name" required /></div>
      <div class="col-auto">
        <select class="field-type form-select">
          ${Object.entries(TYPE_LABELS)
            .map(([value, label]) => `<option value="${value}">${label}</option>`)
            .join("")}
        </select>
      </div>
      <div class="col-auto"><button type="button" class="btn btn-outline-danger remove-field-btn">Remove</button></div>
    `;
    row.querySelector(".remove-field-btn").addEventListener("click", () => {
      if (fieldsContainer.children.length > 1) {
        row.remove();
      }
    });
    fieldsContainer.appendChild(row);
  }

  addFieldRow();
  document.getElementById("add-field-btn").addEventListener("click", addFieldRow);

  document.getElementById("new-table-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.hidden = true;

    const name = document.getElementById("table-name").value.trim();
    const columns = Array.from(fieldsContainer.querySelectorAll(".field-row")).map((row) => ({
      name: row.querySelector(".field-name").value.trim(),
      type: row.querySelector(".field-type").value,
    }));

    try {
      await api("/api/tables", {
        method: "POST",
        body: JSON.stringify({ name, columns }),
      });
      window.location.hash = "#/tables";
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.hidden = false;
    }
  });
}

// ---------------------------------------------------------------------------
// Table Data view
// ---------------------------------------------------------------------------

async function renderTableDataView(slug) {
  setPageTitle("Loading\u2026");
  app.innerHTML = `<section class="view"><p class="text-muted">Loading&hellip;</p></section>`;

  let table;
  try {
    table = await api(`/api/tables/${encodeURIComponent(slug)}`);
  } catch (err) {
    setPageTitle("Table not found");
    app.innerHTML = `
      <section class="view">
        <div class="alert alert-danger">${escapeHtml(err.message)}</div>
        <a class="btn btn-primary" href="#/tables">Back to Tables</a>
      </section>
    `;
    return;
  }

  setPageTitle(table.name);

  const state = {
    tableSlug: table.slug,
    columns: table.columns,
    rows: table.rows,
    sort: { slug: null, dir: "asc" },
    filters: {},
    editingId: null,
  };

  app.innerHTML = `
    <section class="view">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h1 class="h3 mb-0">${escapeHtml(table.name)}</h1>
        <a class="btn btn-outline-secondary" href="#/tables">Back to Tables</a>
      </div>

      <div class="table-responsive mb-4">
        <table class="table table-hover align-middle data-table">
          <thead>
            <tr id="header-row"></tr>
            <tr id="filter-row"></tr>
          </thead>
          <tbody id="data-rows"></tbody>
        </table>
      </div>

      <h2 class="h5" id="form-title">Add record</h2>
      <div class="alert alert-danger" id="row-form-error" hidden></div>
      <form id="row-form" class="card p-3">
        <div class="record-fields row g-3" id="record-fields"></div>
        <div class="form-actions d-flex gap-2 mt-3">
          <button type="submit" class="btn btn-primary" id="row-save-btn">Add</button>
          <button type="button" class="btn btn-outline-secondary" id="row-cancel-btn" hidden>Cancel</button>
        </div>
      </form>
    </section>
  `;

  renderHeaderRow(state);
  renderFilterRow(state);
  renderDataRows(state);
  renderRecordForm(state);

  document.getElementById("row-form").addEventListener("submit", (event) => {
    event.preventDefault();
    saveRecord(slug, state);
  });
  document.getElementById("row-cancel-btn").addEventListener("click", () => {
    exitEditMode(state);
  });
}

function renderHeaderRow(state) {
  const headerRow = document.getElementById("header-row");
  const cells = state.columns
    .map((column) => {
      const isSorted = state.sort.slug === column.slug;
      const arrow = isSorted ? (state.sort.dir === "asc" ? " \u25B2" : " \u25BC") : "";
      return `<th class="sortable" data-slug="${escapeHtml(column.slug)}">${escapeHtml(column.name)}${arrow}</th>`;
    })
    .join("");
  headerRow.innerHTML = `${cells}<th>Actions</th>`;

  headerRow.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const slug = th.dataset.slug;
      if (state.sort.slug === slug) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = { slug, dir: "asc" };
      }
      renderHeaderRow(state);
      renderDataRows(state);
    });
  });
}

function renderFilterRow(state) {
  const filterRow = document.getElementById("filter-row");
  const cells = state.columns
    .map((column) => {
      if (column.filterable === false) {
        return "<th></th>";
      }
      return `
        <th>
          <input
            type="text"
            class="filter-input form-control form-control-sm"
            data-slug="${escapeHtml(column.slug)}"
            placeholder="Filter&hellip;"
            value="${escapeHtml(state.filters[column.slug] || "")}"
          />
        </th>
      `;
    })
    .join("");
  filterRow.innerHTML = `${cells}<th></th>`;

  filterRow.querySelectorAll(".filter-input").forEach((input) => {
    input.addEventListener("input", () => {
      state.filters[input.dataset.slug] = input.value;
      renderDataRows(state);
    });
  });
}

function getVisibleRows(state) {
  let rows = state.rows.slice();

  Object.entries(state.filters).forEach(([slug, text]) => {
    if (!text) return;
    const needle = text.toLowerCase();
    rows = rows.filter((row) => String(row[slug] ?? "").toLowerCase().includes(needle));
  });

  if (state.sort.slug) {
    const { slug, dir } = state.sort;
    const column = state.columns.find((col) => col.slug === slug);
    const factor = dir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      const av = a[slug];
      const bv = b[slug];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (column && NUMERIC_TYPES.has(column.type)) {
        return (av - bv) * factor;
      }
      return String(av).localeCompare(String(bv)) * factor;
    });
  }

  return rows;
}

function renderDataRows(state) {
  const tbody = document.getElementById("data-rows");
  const rows = getVisibleRows(state);

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td class="text-muted" colspan="${state.columns.length + 1}">No records.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows
    .map((row) => {
      const cells = state.columns
        .map((column) => `<td>${escapeHtml(row[column.slug])}</td>`)
        .join("");
      return `
        <tr data-id="${row.id}">
          ${cells}
          <td class="actions-cell">
            <button type="button" class="btn btn-sm btn-outline-secondary edit-btn">Edit</button>
            <button type="button" class="btn btn-sm btn-outline-danger delete-btn">Delete</button>
          </td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    const id = Number(tr.dataset.id);
    const row = state.rows.find((r) => r.id === id);
    tr.querySelector(".edit-btn").addEventListener("click", () => enterEditMode(state, row));
    tr.querySelector(".delete-btn").addEventListener("click", () => deleteRecord(state, id));
  });
}

function renderRecordForm(state) {
  const container = document.getElementById("record-fields");
  container.innerHTML = state.columns
    .filter((column) => column.editable !== false)
    .map((column) => {
      const inputType = NUMERIC_TYPES.has(column.type) ? "number" : "text";
      const step = column.type === "integer" ? "1" : column.type === "number" ? "any" : null;
      return `
        <div class="col-md-4">
          <label class="form-label">${escapeHtml(column.name)}</label>
          <input type="${inputType}" class="record-input form-control" data-slug="${escapeHtml(column.slug)}" ${
        step ? `step="${step}"` : ""
      } />
        </div>
      `;
    })
    .join("");
}

function fillRecordForm(state, row) {
  document.querySelectorAll(".record-input").forEach((input) => {
    const value = row[input.dataset.slug];
    input.value = value == null ? "" : value;
  });
}

function clearRecordForm() {
  document.querySelectorAll(".record-input").forEach((input) => {
    input.value = "";
  });
}

function enterEditMode(state, row) {
  state.editingId = row.id;
  document.getElementById("form-title").textContent = "Edit record";
  document.getElementById("row-save-btn").textContent = "Save changes";
  document.getElementById("row-cancel-btn").hidden = false;
  fillRecordForm(state, row);
  document.getElementById("row-form").scrollIntoView({ behavior: "smooth", block: "center" });
}

function exitEditMode(state) {
  state.editingId = null;
  document.getElementById("form-title").textContent = "Add record";
  document.getElementById("row-save-btn").textContent = "Add";
  document.getElementById("row-cancel-btn").hidden = true;
  clearRecordForm();
}

async function saveRecord(slug, state) {
  const errorEl = document.getElementById("row-form-error");
  errorEl.hidden = true;

  const payload = {};
  document.querySelectorAll(".record-input").forEach((input) => {
    payload[input.dataset.slug] = input.value;
  });

  try {
    if (state.editingId == null) {
      const created = await api(`/api/tables/${encodeURIComponent(slug)}/rows`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.rows.push(created);
    } else {
      const updated = await api(
        `/api/tables/${encodeURIComponent(slug)}/rows/${state.editingId}`,
        { method: "PUT", body: JSON.stringify(payload) }
      );
      const index = state.rows.findIndex((row) => row.id === state.editingId);
      state.rows[index] = updated;
    }
    exitEditMode(state);
    renderDataRows(state);
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  }
}

async function deleteRecord(state, id) {
  if (!window.confirm("Delete this record?")) return;
  try {
    await api(`/api/tables/${encodeURIComponent(state.tableSlug)}/rows/${id}`, {
      method: "DELETE",
    });
  } catch (err) {
    window.alert(err.message);
    return;
  }
  state.rows = state.rows.filter((row) => row.id !== id);
  if (state.editingId === id) {
    exitEditMode(state);
  }
  renderDataRows(state);
}
