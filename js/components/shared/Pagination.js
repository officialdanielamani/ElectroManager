// js/components/shared/Pagination.js

// Ensure the global namespace exists
window.App = window.App || {};
window.App.components = window.App.components || {};
window.App.components.shared = window.App.components.shared || {};

/**
* Pagination - Reusable pagination component
*/
window.App.components.shared.Pagination = ({
   // Pagination data
   currentPage = 1,
   totalPages = 1,
   totalItems = 0,
   itemsPerPage = 'all',
   
   // Display options
   maxVisiblePages = 5,
   showInfo = true,
   showJumpToPage = false,
   
   // Event handlers
   onPageChange,
   
   // Styling
   className = '',
   size = 'default' // 'small', 'default', 'large'
}) => {
   const { UI } = window.App.utils;
   const { useState } = React;
   
   // Internal state for jump to page
   const [jumpToPageInput, setJumpToPageInput] = useState('');
   
   // Don't render if showing all items or only one page
   if (itemsPerPage === 'all' || totalPages <= 1) {
       return null;
   }
   
   // Handle page change with validation
   const handlePageChange = (page) => {
       const validPage = Math.min(Math.max(1, page), totalPages);
       if (validPage !== currentPage && onPageChange) {
           onPageChange(validPage);
       }
   };
   
   // Handle jump to page
   const handleJumpToPage = () => {
       const targetPage = parseInt(jumpToPageInput, 10);
       if (!isNaN(targetPage) && targetPage >= 1 && targetPage <= totalPages) {
           handlePageChange(targetPage);
           setJumpToPageInput('');
       }
   };
   
   // Generate page numbers to display
   const generatePageNumbers = () => {
       const pages = [];
       let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
       let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
       
       // Adjust if we're near the end
       if (endPage - startPage + 1 < maxVisiblePages) {
           startPage = Math.max(1, endPage - maxVisiblePages + 1);
       }
       
       // Add first page if not in range
       if (startPage > 1) {
           pages.push(1);
           if (startPage > 2) {
               pages.push('...');
           }
       }
       
       // Add visible page numbers
       for (let i = startPage; i <= endPage; i++) {
           pages.push(i);
       }
       
       // Add last page if not in range
       if (endPage < totalPages) {
           if (endPage < totalPages - 1) {
               pages.push('...');
           }
           pages.push(totalPages);
       }
       
       return pages;
   };
   
   // Size-based classes
   const sizeClasses = {
       small: 'text-sm px-2 py-1',
       default: 'px-3 py-2',
       large: 'px-4 py-3 text-lg'
   };
   
   const buttonClass = sizeClasses[size] || sizeClasses.default;
   const disabledClass = `${buttonClass} text-gray-400 cursor-not-allowed bg-gray-50`;
   const activeClass = `${buttonClass} bg-${UI.getThemeColors().primary} text-white`;
   const normalClass = `${buttonClass} bg-${UI.getThemeColors().cardBackground} text-${UI.getThemeColors().textSecondary} hover:bg-${UI.getThemeColors().background} border border-${UI.getThemeColors().border}`;
   
   const pageNumbers = generatePageNumbers();
   
   return React.createElement('div', { 
       className: `flex flex-col items-center space-y-4 ${className}` 
   },
       // Main pagination controls
       React.createElement('div', { className: "flex justify-center items-center space-x-1" },
           // Previous button
           React.createElement('button', {
               onClick: () => handlePageChange(currentPage - 1),
               disabled: currentPage === 1,
               className: `${currentPage === 1 ? disabledClass : normalClass} rounded-l`,
               'aria-label': 'Previous page'
           },
               React.createElement('svg', {
                   xmlns: "http://www.w3.org/2000/svg",
                   className: "h-5 w-5",
                   fill: "none",
                   viewBox: "0 0 24 24",
                   stroke: "currentColor"
               },
                   React.createElement('path', {
                       strokeLinecap: "round",
                       strokeLinejoin: "round",
                       strokeWidth: 2,
                       d: "M15 19l-7-7 7-7"
                   })
               )
           ),
           
           // Page numbers
           pageNumbers.map((page, index) => {
               if (page === '...') {
                   return React.createElement('span', {
                       key: `ellipsis-${index}`,
                       className: `${buttonClass} text-gray-500 bg-transparent`
                   }, '...');
               }
               
               return React.createElement('button', {
                   key: page,
                   onClick: () => handlePageChange(page),
                   className: page === currentPage ? activeClass : normalClass,
                   'aria-label': `Page ${page}`,
                   'aria-current': page === currentPage ? 'page' : undefined
               }, page.toString());
           }),
           
           // Next button
           React.createElement('button', {
               onClick: () => handlePageChange(currentPage + 1),
               disabled: currentPage === totalPages,
               className: `${currentPage === totalPages ? disabledClass : normalClass} rounded-r`,
               'aria-label': 'Next page'
           },
               React.createElement('svg', {
                   xmlns: "http://www.w3.org/2000/svg",
                   className: "h-5 w-5",
                   fill: "none",
                   viewBox: "0 0 24 24",
                   stroke: "currentColor"
               },
                   React.createElement('path', {
                       strokeLinecap: "round",
                       strokeLinejoin: "round",
                       strokeWidth: 2,
                       d: "M9 5l7 7-7 7"
                   })
               )
           )
       ),
       
       // Jump to page (if enabled)
       showJumpToPage && React.createElement('div', { className: "flex items-center space-x-2" },
           React.createElement('span', {
               className: `text-sm text-${UI.getThemeColors().textSecondary}`
           }, "Go to page:"),
           React.createElement('input', {
               type: "number",
               min: "1",
               max: totalPages.toString(),
               value: jumpToPageInput,
               onChange: (e) => setJumpToPageInput(e.target.value),
               onKeyDown: (e) => {
                   if (e.key === 'Enter') {
                       handleJumpToPage();
                   }
               },
               className: `w-16 ${UI.forms.input} text-center`,
               placeholder: currentPage.toString()
           }),
           React.createElement('button', {
               onClick: handleJumpToPage,
               className: UI.buttons.small.primary
           }, "Go")
       ),
       
       // Pagination info
       showInfo && totalItems > 0 && React.createElement('div', {
           className: `text-center text-sm text-${UI.getThemeColors().textSecondary}`
       },
           `Showing ${(currentPage - 1) * itemsPerPage + 1}-${Math.min(currentPage * itemsPerPage, totalItems)} of ${totalItems} items`
       )
   );
};

console.log("Pagination loaded");