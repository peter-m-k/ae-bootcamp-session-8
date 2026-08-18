/**
 * Vanilla-JS single page app: hash-based router with three views
 * (Tables list, New Table form, Table Data grid).
 */

const app = document.getElementById("app");

const TYPE_LABELS = {
  text: "Text",
  number: "Number",
};

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
  app.innerHTML = `
    <section class="view">
      <div class="view-header">
        <h1>Tables</h1>
        <a class="button" href="#/tables/new">+ Add Table</a>
      </div>
      <ul class="table-list" id="table-list"><li class="muted">Loading&hellip;</li></ul>
    </section>
  `;

  const listEl = document.getElementById("table-list");
  try {
    const tables = await api("/api/tables");
    if (tables.length === 0) {
      listEl.innerHTML = `<li class="muted">No tables yet. Add one to get started.</li>`;
      return;
    }
    listEl.innerHTML = tables
      .map(
        (table) => `
          <li>
            <a href="#/tables/${encodeURIComponent(table.slug)}">${escapeHtml(table.name)}</a>
          </li>
        `
      )
      .join("");
  } catch (err) {
    listEl.innerHTML = `<li class="error">${escapeHtml(err.message)}</li>`;
  }
}

// ---------------------------------------------------------------------------
// New Table view
// ---------------------------------------------------------------------------

function renderNewTableView() {
  app.innerHTML = `
    <section class="view">
      <div class="view-header">
        <h1>New Table</h1>
        <a class="button secondary" href="#/tables">Cancel</a>
      </div>
      <p class="error" id="form-error" hidden></p>
      <form id="new-table-form">
        <label class="field">
          <span>Table name</span>
          <input type="text" id="table-name" required />
        </label>

        <div id="fields-container"></div>

        <button type="button" class="button secondary" id="add-field-btn">+ Add field</button>

        <div class="form-actions">
          <button type="submit" class="button primary">Save</button>
        </div>
      </form>
    </section>
  `;

  const fieldsContainer = document.getElementById("fields-container");
  const errorEl = document.getElementById("form-error");

  function addFieldRow() {
    const row = document.createElement("div");
    row.className = "field-row";
    row.innerHTML = `
      <input type="text" class="field-name" placeholder="Field name" required />
      <select class="field-type">
        ${Object.entries(TYPE_LABELS)
          .map(([value, label]) => `<option value="${value}">${label}</option>`)
          .join("")}
      </select>
      <button type="button" class="button secondary remove-field-btn">Remove</button>
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
  app.innerHTML = `<section class="view"><p class="muted">Loading&hellip;</p></section>`;

  let table;
  try {
    table = await api(`/api/tables/${encodeURIComponent(slug)}`);
  } catch (err) {
    app.innerHTML = `
      <section class="view">
        <p class="error">${escapeHtml(err.message)}</p>
        <a class="button" href="#/tables">Back to Tables</a>
      </section>
    `;
    return;
  }

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
      <div class="view-header">
        <h1>${escapeHtml(table.name)}</h1>
        <a class="button secondary" href="#/tables">Back to Tables</a>
      </div>

      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr id="header-row"></tr>
            <tr id="filter-row"></tr>
          </thead>
          <tbody id="data-rows"></tbody>
        </table>
      </div>

      <h2 id="form-title">Add record</h2>
      <p class="error" id="row-form-error" hidden></p>
      <form id="row-form">
        <div class="record-fields" id="record-fields"></div>
        <div class="form-actions">
          <button type="submit" class="button primary" id="row-save-btn">Add</button>
          <button type="button" class="button secondary" id="row-cancel-btn" hidden>Cancel</button>
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
    .map(
      (column) => `
        <th>
          <input
            type="text"
            class="filter-input"
            data-slug="${escapeHtml(column.slug)}"
            placeholder="Filter&hellip;"
            value="${escapeHtml(state.filters[column.slug] || "")}"
          />
        </th>
      `
    )
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
      if (column && column.type === "number") {
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
    tbody.innerHTML = `<tr><td class="muted" colspan="${state.columns.length + 1}">No records.</td></tr>`;
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
            <button type="button" class="button secondary edit-btn">Edit</button>
            <button type="button" class="button danger delete-btn">Delete</button>
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
    .map((column) => {
      const inputType = column.type === "number" ? "number" : "text";
      return `
        <label class="field">
          <span>${escapeHtml(column.name)}</span>
          <input type="${inputType}" class="record-input" data-slug="${escapeHtml(column.slug)}" ${
        column.type === "number" ? "step='any'" : ""
      } />
        </label>
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
