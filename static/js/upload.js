/**
 * upload.js — Upload form UX enhancements for intake.
 */
(function() {
  'use strict';

  const form = document.getElementById('upload-form');
  if (!form) return;

  const btn = document.getElementById('upload-btn');
  const spinner = document.getElementById('upload-spinner');

  form.addEventListener('submit', function() {
    if (btn) btn.disabled = true;
    if (spinner) spinner.classList.remove('d-none');
  });
})();
