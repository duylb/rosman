(() => {
  const normalizeValue = (value) => value.replace(/\s+/g, " ").trim().toLowerCase();

  function sortTable(table, columnIndex, direction) {
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll("tr"));
    const sortableRows = rows.filter((row) => row.children.length > columnIndex);

    sortableRows.sort((a, b) => {
      const left = normalizeValue(a.children[columnIndex].innerText || "");
      const right = normalizeValue(b.children[columnIndex].innerText || "");

      if (left < right) return direction === "asc" ? -1 : 1;
      if (left > right) return direction === "asc" ? 1 : -1;
      return 0;
    });

    sortableRows.forEach((row) => tbody.appendChild(row));
  }

  const applySort = (header) => {
    const table = header.closest("table");
    const headerRow = header.parentNode;
    if (!table || !headerRow) return;

    const columnIndex = Array.from(headerRow.children).indexOf(header);
    if (columnIndex < 0) return;

    const direction = header.dataset.sortDirection === "desc" ? "desc" : "asc";
    sortTable(table, columnIndex, direction);

    const nextDirection = direction === "asc" ? "desc" : "asc";
    header.dataset.sortDirection = nextDirection;

    headerRow.querySelectorAll("th.sortable").forEach((cell) => {
      if (cell !== header) {
        cell.classList.remove("sortable-asc", "sortable-desc");
        cell.setAttribute("aria-sort", "none");
      }
    });

    header.classList.remove("sortable-asc", "sortable-desc");
    header.classList.add(direction === "asc" ? "sortable-asc" : "sortable-desc");
    header.setAttribute("aria-sort", direction === "asc" ? "ascending" : "descending");
  };

  document.querySelectorAll("th.sortable").forEach((header) => {
    header.dataset.sortDirection = "asc";
    header.setAttribute("role", "button");
    header.setAttribute("tabindex", "0");
    header.setAttribute("aria-sort", "none");

    header.addEventListener("click", () => applySort(header));
    header.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        applySort(header);
      }
    });
  });
})();
