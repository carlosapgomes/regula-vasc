/**
 * doctor_queue_filter.js — Client-side filtering for the doctor queue.
 *
 * Allows filtering the pending cases list by patient name or record number.
 */
(function() {
  'use strict';

  var filterInput = document.getElementById('queue-filter-input');
  if (!filterInput) return;

  filterInput.addEventListener('input', function() {
    var query = this.value.toLowerCase().trim();
    var items = document.querySelectorAll('#pending-list .list-group-item');

    items.forEach(function(item) {
      var text = item.textContent.toLowerCase();
      if (!query || text.indexOf(query) !== -1) {
        item.style.display = '';
      } else {
        item.style.display = 'none';
      }
    });
  });
})();
