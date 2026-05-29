// Client-side table sorting for inventory items
// Handles sorting without server calls

class TableSorter {
  constructor(tableId = 'itemTable', opts = {}) {
    this.table = document.getElementById(tableId);
    this.tbody = this.table?.querySelector('tbody');
    this.headers = this.table?.querySelectorAll('thead th');
    this.currentSort = { column: null, direction: 'asc' };
    this.skipLast = opts.skipLast !== false; // default true; pass false to sort all non-checkbox cols

    if (this.table && this.headers) {
      this.init();
    }
  }

  init() {
    // Attach click handlers to sortable headers
    this.headers.forEach((header, index) => {
      // Always skip checkbox column (index 0); skip last only if skipLast is true
      if (index === 0) return;
      if (this.skipLast && index === this.headers.length - 1) return;
      
      const link = header.querySelector('a');
      if (link) {
        // Set href to javascript:void(0) to prevent any navigation
        link.href = 'javascript:void(0)';
        link.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.handleSort(header, index);
        });
        header.style.cursor = 'pointer';
      }
    });
  }

  handleSort(header, columnIndex) {
    const link = header.querySelector('a');
    if (!link) return;

    // Determine sort direction
    let direction = 'asc';
    if (this.currentSort.column === columnIndex && this.currentSort.direction === 'asc') {
      direction = 'desc';
    }

    this.currentSort = { column: columnIndex, direction };
    this.sortTable(columnIndex, direction);
    this.updateHeaders(columnIndex, direction);
  }

  sortTable(columnIndex, direction) {
    const rows = Array.from(this.tbody.querySelectorAll('tr'));

    rows.sort((a, b) => {
      const aVal = a.cells[columnIndex].textContent.trim();
      const bVal = b.cells[columnIndex].textContent.trim();

      // Natural sort: handles "R3 < R4" and alphabetical correctly.
      // localeCompare with numeric:true avoids the "strip-digits" trick that
      // misclassifies product names like "LX-PB225M" as negative numbers.
      const comparison = aVal.localeCompare(bVal, undefined, { numeric: true, sensitivity: 'base' });

      return direction === 'asc' ? comparison : -comparison;
    });

    // Re-append sorted rows
    rows.forEach(row => this.tbody.appendChild(row));
  }

  updateHeaders(activeColumnIndex, direction) {
    this.headers.forEach((header, index) => {
      const icon = header.querySelector('i');
      if (!icon) return;

      icon.className = 'bi';

      if (index === activeColumnIndex) {
        icon.className = direction === 'asc' ? 'bi bi-sort-up' : 'bi bi-sort-down';
      } else {
        icon.className = 'bi bi-arrow-down-up text-muted sort-default';
      }
    });
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  new TableSorter('itemTable');
});
