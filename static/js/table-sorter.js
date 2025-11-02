// Client-side table sorting for inventory items
// Handles sorting without server calls

class TableSorter {
  constructor(tableId = 'itemTable') {
    this.table = document.getElementById(tableId);
    this.tbody = this.table?.querySelector('tbody');
    this.headers = this.table?.querySelectorAll('thead th');
    this.currentSort = { column: null, direction: 'asc' };
    
    if (this.table && this.headers) {
      this.init();
    }
  }

  init() {
    // Attach click handlers to sortable headers
    this.headers.forEach((header, index) => {
      // Skip checkbox column and action column
      if (index === 0 || index === this.headers.length - 1) return;
      
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
      let aVal = a.cells[columnIndex].textContent.trim();
      let bVal = b.cells[columnIndex].textContent.trim();

      // Try to detect data type
      const aNum = parseFloat(aVal.replace(/[^\d.-]/g, ''));
      const bNum = parseFloat(bVal.replace(/[^\d.-]/g, ''));

      let comparison = 0;

      // Numeric comparison if both are numbers
      if (!isNaN(aNum) && !isNaN(bNum)) {
        comparison = aNum - bNum;
      } else {
        // String comparison (case-insensitive)
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
        comparison = aVal.localeCompare(bVal);
      }

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
