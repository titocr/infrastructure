/* Navigation is page links only; page headings never change its structure. */
const navigation = document.getElementById('site-navigation');
const toggle = document.querySelector('.nav-toggle');
if (navigation && toggle) {
  document.documentElement.classList.add('js');
  toggle.hidden = false;
  const closeMenu = () => {
    navigation.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.textContent = 'Menu';
  };
  toggle.addEventListener('click', () => {
    const open = navigation.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? 'Close menu' : 'Menu';
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navigation.classList.contains('is-open')) {
      closeMenu();
      toggle.focus();
    }
  });
  // Preserve the position chosen by the reader rather than jumping to the active page.
  const desktop = window.matchMedia('(min-width: 761px)');
  try {
    if (desktop.matches) navigation.scrollTop = Number(sessionStorage.getItem('manual-nav-scroll') || 0);
    navigation.addEventListener('scroll', () => {
      if (desktop.matches) {
        try { sessionStorage.setItem('manual-nav-scroll', String(navigation.scrollTop)); } catch (_) {}
      }
    });
  } catch (_) { /* Navigation works when browser storage is unavailable. */ }
  desktop.addEventListener('change', closeMenu);
}
for (const table of document.querySelectorAll('main table')) {
  const region = document.createElement('div');
  region.className = 'table-scroll';
  region.setAttribute('role', 'region');
  region.setAttribute('aria-label', 'Scrollable table');
  table.before(region);
  region.append(table);
  const update = () => {
    if (region.scrollWidth > region.clientWidth) region.tabIndex = 0;
    else region.removeAttribute('tabindex');
  };
  update();
  new ResizeObserver(update).observe(region);
}
