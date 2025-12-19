// Simple demo JS for theme preview and UI interactions (static demo)
document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  // initialize theme from localStorage
  const saved = localStorage.getItem('villicus_theme') || 'light';
  body.setAttribute('data-theme', saved);

  // theme swatches on index
  // Make theme controls keyboard accessible and announce changes
  const announcer = document.createElement('div');
  announcer.className = 'sr-only';
  announcer.setAttribute('aria-live', 'polite');
  document.body.appendChild(announcer);

  document.querySelectorAll('[data-theme]').forEach(el => {
    // ensure focusable for non-button elements
    if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
    const apply = (t) => {
      body.setAttribute('data-theme', t);
      localStorage.setItem('villicus_theme', t);
      announcer.textContent = `Theme set to ${t}`;
    };
    el.addEventListener('click', () => apply(el.getAttribute('data-theme')));
    el.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); apply(el.getAttribute('data-theme')); }
    });
  });

  // Demo sign-in anchor: show guideline
  document.querySelectorAll('a[href="#signin"]').forEach(a => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      alert('This demo is static. To enable sign-in, host the backend and point Sign-in to its /login endpoint.');
    });
  });
});

// Helper for configure demo (loaded by configure_111111.html)
async function demoAddRole(roleId, level) {
  const list = document.getElementById('staff-list');
  const row = document.createElement('div');
  row.className = 'card';
  row.style.display = 'flex'; row.style.justifyContent='space-between'; row.style.alignItems='center'; row.style.marginBottom='8px';
  row.innerHTML = `<div>Role ${roleId} — Level ${level}</div><button class="btn btn-ghost" onclick="(function(el){el.parentElement.remove();})(this)">Remove</button>`;
  list.prepend(row);
}

function demoSetWarns(n, action){
  document.getElementById('warn-current').textContent = `${n} warns → ${action}`;
  localStorage.setItem('demo_warns', JSON.stringify({n,action}));
  // Gentle non-blocking feedback for demo
  const t = document.createElement('div');
  t.className = 'sr-only';
  t.textContent = `Warns updated: ${n} → ${action}`;
  document.body.appendChild(t);
}

// Expose to global for demo HTML buttons
window.demoAddRole = demoAddRole;
window.demoSetWarns = demoSetWarns;
