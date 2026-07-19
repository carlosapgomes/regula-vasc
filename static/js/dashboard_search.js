/**
 * Dashboard search — server-side with minimum 3 characters.
 * Auto-submit when the search field loses focus or after a debounce delay.
 */
(function () {
  'use strict';

  var searchInput = document.querySelector('input[name="q"]');
  if (!searchInput) return;

  var debounceTimer = null;
  var DEBOUNCE_DELAY = 600; // ms

  function doSearch() {
    var value = searchInput.value.trim();
    if (value.length >= 3 || value.length === 0) {
      searchInput.closest('form').submit();
    } else if (value.length > 0 && value.length < 3) {
      // Show a hint
      var helpBlock = searchInput.parentElement.querySelector('.search-help');
      if (!helpBlock) {
        helpBlock = document.createElement('small');
        helpBlock.className = 'search-help text-warning ms-2';
        helpBlock.textContent = 'Mínimo de 3 caracteres';
        searchInput.parentElement.appendChild(helpBlock);
      }
    }
  }

  searchInput.addEventListener('input', function () {
    // Remove help block on input change
    var helpBlock = searchInput.parentElement.querySelector('.search-help');
    if (helpBlock) helpBlock.remove();

    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(doSearch, DEBOUNCE_DELAY);
  });

  searchInput.addEventListener('blur', function () {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    var value = searchInput.value.trim();
    if (value.length >= 3 || value.length === 0) {
      searchInput.closest('form').submit();
    }
  });
})();
