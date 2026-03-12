(() => {
  const root = document.getElementById("sales-dashboard");
  if (!root) return;

  const startInput = document.getElementById("report-start-date");
  const endInput = document.getElementById("report-end-date");
  const viewButton = document.getElementById("view-report-btn");
  const statusEl = document.getElementById("dashboard-status");
  const toggleUploadButton = document.getElementById("toggle-upload-btn");
  const uploadPanel = document.getElementById("upload-panel");

  const searchInput = document.getElementById("table-search-input");
  const pageSizeSelect = document.getElementById("table-page-size");
  const prevButton = document.getElementById("table-prev-page");
  const nextButton = document.getElementById("table-next-page");
  const pageLabel = document.getElementById("table-page-label");
  const tableBody = document.getElementById("sales-table-body");
  const sortButtons = Array.from(document.querySelectorAll(".table-sort"));

  const exportCsvLink = document.getElementById("export-csv-link");
  const exportExcelLink = document.getElementById("export-excel-link");
  const exportPdfLink = document.getElementById("export-pdf-link");

  const moneyFormatter = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const intFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

  const state = {
    rows: [],
    sortKey: "net_revenue",
    sortDirection: "desc",
    page: 1,
    pageSize: Number(pageSizeSelect?.value || 10),
    charts: {
      revenueBar: null,
      revenuePie: null,
      returnNet: null,
    },
  };

  function formatMoney(value) {
    return moneyFormatter.format(Number(value || 0));
  }

  function formatInt(value) {
    return intFormatter.format(Number(value || 0));
  }

  function setStatus(message, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("text-danger", Boolean(isError));
    statusEl.classList.toggle("text-muted", !isError);
  }

  function queryParams() {
    const start = (startInput?.value || root.dataset.defaultStart || "").trim();
    const end = (endInput?.value || root.dataset.defaultEnd || "").trim();
    const params = new URLSearchParams();
    if (start) params.set("start_date", start);
    if (end) params.set("end_date", end);
    return params;
  }

  function updateExportLinks() {
    const params = queryParams().toString();
    if (exportCsvLink) exportCsvLink.href = `${root.dataset.exportCsvUrl}?${params}`;
    if (exportExcelLink) exportExcelLink.href = `${root.dataset.exportExcelUrl}?${params}`;
    if (exportPdfLink) exportPdfLink.href = `${root.dataset.exportPdfUrl}?${params}`;
  }

  function updateSummary(summary) {
    document.getElementById("stat-total-revenue").textContent = formatMoney(summary.total_revenue);
    document.getElementById("stat-returned-amount").textContent = formatMoney(summary.total_return_value);
    document.getElementById("stat-net-revenue").textContent = formatMoney(summary.net_revenue);
    document.getElementById("stat-units-sold").textContent = formatInt(summary.total_units_sold);
    document.getElementById("stat-returned-units").textContent = formatInt(summary.total_return_units);
    document.getElementById("stat-product-count").textContent = formatInt(summary.product_count);
  }

  function chartLabels(rows, limit) {
    return rows.slice(0, limit).map((row) => `${row.item_code} - ${row.item_name}`);
  }

  function destroyCharts() {
    Object.values(state.charts).forEach((chart) => {
      if (chart) chart.destroy();
    });
  }

  function renderCharts(rows) {
    destroyCharts();

    const topBar = rows.slice(0, 12);
    const barCtx = document.getElementById("chart-revenue-bar");
    state.charts.revenueBar = new Chart(barCtx, {
      type: "bar",
      data: {
        labels: chartLabels(topBar, 12),
        datasets: [
          {
            label: "Revenue",
            data: topBar.map((row) => Number(row.revenue || 0)),
            backgroundColor: "#2563eb",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: "Revenue by product (Top 12)" },
          legend: { display: true },
          tooltip: { enabled: true },
        },
        scales: {
          x: { title: { display: true, text: "Products" } },
          y: { beginAtZero: true, title: { display: true, text: "Revenue" } },
        },
      },
    });

    const pieSource = rows.slice(0, 8);
    const remainingRevenue = rows.slice(8).reduce((sum, row) => sum + Number(row.revenue || 0), 0);
    const pieLabels = pieSource.map((row) => row.item_code);
    const pieData = pieSource.map((row) => Number(row.revenue || 0));
    if (remainingRevenue > 0) {
      pieLabels.push("Other");
      pieData.push(remainingRevenue);
    }
    const pieCtx = document.getElementById("chart-revenue-pie");
    state.charts.revenuePie = new Chart(pieCtx, {
      type: "pie",
      data: {
        labels: pieLabels,
        datasets: [
          {
            label: "Revenue distribution",
            data: pieData,
            backgroundColor: ["#1d4ed8", "#0ea5e9", "#22c55e", "#eab308", "#ef4444", "#8b5cf6", "#f97316", "#14b8a6", "#64748b"],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: "Revenue distribution by product" },
          legend: { display: true, position: "bottom" },
          tooltip: { enabled: true },
        },
      },
    });

    const returnNetRows = rows.slice(0, 10);
    const returnNetCtx = document.getElementById("chart-return-net");
    state.charts.returnNet = new Chart(returnNetCtx, {
      type: "bar",
      data: {
        labels: returnNetRows.map((row) => row.item_code),
        datasets: [
          {
            label: "Returned amount",
            data: returnNetRows.map((row) => Number(row.return_amount || 0)),
            backgroundColor: "#f59e0b",
          },
          {
            label: "Net revenue",
            data: returnNetRows.map((row) => Number(row.net_revenue || 0)),
            backgroundColor: "#16a34a",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          title: { display: true, text: "Returned amount vs net revenue (Top 10)" },
          legend: { display: true },
          tooltip: { enabled: true },
        },
        scales: {
          x: { title: { display: true, text: "Products" } },
          y: { beginAtZero: true, title: { display: true, text: "Amount" } },
        },
      },
    });
  }

  function filteredRows() {
    const keyword = (searchInput?.value || "").trim().toLowerCase();
    let rows = state.rows;
    if (keyword) {
      rows = rows.filter((row) => {
        const code = String(row.item_code || "").toLowerCase();
        const name = String(row.item_name || "").toLowerCase();
        return code.includes(keyword) || name.includes(keyword);
      });
    }

    const direction = state.sortDirection === "asc" ? 1 : -1;
    rows = [...rows].sort((a, b) => {
      const av = a[state.sortKey];
      const bv = b[state.sortKey];
      if (typeof av === "number" || typeof bv === "number") {
        return (Number(av || 0) - Number(bv || 0)) * direction;
      }
      return String(av || "").localeCompare(String(bv || ""), undefined, { sensitivity: "base", numeric: true }) * direction;
    });
    return rows;
  }

  function renderTable() {
    const rows = filteredRows();
    const total = rows.length;
    const pageSize = Math.max(1, state.pageSize);
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    state.page = Math.min(Math.max(1, state.page), totalPages);
    const startIndex = (state.page - 1) * pageSize;
    const pagedRows = rows.slice(startIndex, startIndex + pageSize);

    tableBody.innerHTML = "";
    if (!pagedRows.length) {
      tableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No rows found for selected filters.</td></tr>';
    } else {
      pagedRows.forEach((row) => {
        const tr = document.createElement("tr");

        const values = [
          row.item_code || "",
          row.item_name || "",
          formatInt(row.units_sold),
          formatMoney(row.revenue),
          formatInt(row.return_quantity),
          formatMoney(row.return_amount),
          formatMoney(row.net_revenue),
        ];
        values.forEach((value) => {
          const td = document.createElement("td");
          td.textContent = String(value);
          tr.appendChild(td);
        });
        tableBody.appendChild(tr);
      });
    }

    if (pageLabel) {
      if (!total) {
        pageLabel.textContent = "0 items";
      } else {
        pageLabel.textContent = `${startIndex + 1}-${Math.min(startIndex + pagedRows.length, total)} of ${total} items`;
      }
    }
    if (prevButton) prevButton.disabled = state.page <= 1;
    if (nextButton) nextButton.disabled = state.page >= totalPages;
  }

  function renderSortIndicators() {
    sortButtons.forEach((button) => {
      const key = button.dataset.key;
      if (key === state.sortKey) {
        button.textContent = `${button.textContent.replace(/[\^v]/g, "").trim()} ${state.sortDirection === "asc" ? "^" : "v"}`;
      } else {
        button.textContent = button.textContent.replace(/[\^v]/g, "").trim();
      }
    });
  }

  async function loadReport() {
    const start = (startInput?.value || "").trim();
    const end = (endInput?.value || "").trim();
    if (!start || !end) {
      setStatus("Start date and end date are required.", true);
      return;
    }

    setStatus("Loading report data...");
    updateExportLinks();
    const url = `${root.dataset.apiUrl}?${queryParams().toString()}`;

    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      let payload = null;

      if (contentType.includes("application/json")) {
        payload = await response.json();
      } else {
        const rawBody = await response.text();
        if (response.status === 401 || response.status === 403 || response.redirected || rawBody.toLowerCase().includes("<!doctype")) {
          throw new Error("Your session may have expired. Please refresh and log in again.");
        }
        throw new Error("Sales report API returned an unexpected response format.");
      }

      if (!response.ok) {
        throw new Error((payload && payload.message) || "Failed to load report.");
      }

      state.rows = Array.isArray(payload.products) ? payload.products : [];
      state.page = 1;
      updateSummary(payload.summary || {});
      renderCharts(state.rows);
      renderTable();
      setStatus(`Showing report from ${start} to ${end}.`);
    } catch (error) {
      setStatus(error.message || "Unable to load report.", true);
    }
  }

  sortButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.key;
      if (!key) return;
      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDirection = key === "item_code" || key === "item_name" ? "asc" : "desc";
      }
      renderSortIndicators();
      renderTable();
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.page = 1;
      renderTable();
    });
  }
  if (pageSizeSelect) {
    pageSizeSelect.addEventListener("change", () => {
      state.pageSize = Number(pageSizeSelect.value || 10);
      state.page = 1;
      renderTable();
    });
  }
  if (prevButton) {
    prevButton.addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      renderTable();
    });
  }
  if (nextButton) {
    nextButton.addEventListener("click", () => {
      state.page += 1;
      renderTable();
    });
  }
  if (viewButton) {
    viewButton.addEventListener("click", loadReport);
  }
  if (toggleUploadButton && uploadPanel) {
    toggleUploadButton.addEventListener("click", () => {
      uploadPanel.classList.toggle("d-none");
    });
  }

  renderSortIndicators();
  updateExportLinks();
  loadReport();
})();
