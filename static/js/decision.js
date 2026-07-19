/**
 * decision.js — Heartbeat renew for doctor decision lock.
 *
 * Automatically renews the lock token every 4 minutes.
 * Releases lock on page unload.
 */
(function() {
  'use strict';

  const lockInput = document.getElementById('lock-token');
  if (!lockInput) return;

  const token = lockInput.value;
  if (!token) return;

  // Extract case_id from URL pattern: /doctor/cases/<uuid>/
  const match = window.location.pathname.match(/\/doctor\/cases\/([a-f0-9-]+)\//);
  if (!match) return;
  const caseId = match[1];

  const renewUrl = '/doctor/cases/' + caseId + '/lock/renew/';
  const releaseUrl = '/doctor/cases/' + caseId + '/lock/release/';

  // Renew every 4 minutes
  setInterval(function() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', renewUrl, true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.setRequestHeader('X-CSRFToken', getCSRFToken());

    xhr.onload = function() {
      if (xhr.status === 200) {
        try {
          var resp = JSON.parse(xhr.responseText);
          if (!resp.success) {
            console.warn('Lock renewal failed:', resp.error);
          }
        } catch(e) {
          console.warn('Failed to parse lock renewal response');
        }
      }
    };

    xhr.send('lock_token=' + encodeURIComponent(token));
  }, 240000); // 4 minutes

  // Release lock on page unload
  window.addEventListener('beforeunload', function() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', releaseUrl, false); // synchronous
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.setRequestHeader('X-CSRFToken', getCSRFToken());
    xhr.send('lock_token=' + encodeURIComponent(token));
  });

  function getCSRFToken() {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var c = cookies[i].trim();
      if (c.startsWith('csrftoken=')) {
        return c.substring('csrftoken='.length, c.length);
      }
    }
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }
})();
