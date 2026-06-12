(function () {
  const menuToggle = document.querySelector('.menu-toggle');
  const mobileNav = document.querySelector('.mobile-nav');

  menuToggle?.addEventListener('click', () => {
    const isOpen = !mobileNav.hasAttribute('hidden');
    mobileNav.toggleAttribute('hidden', isOpen);
    menuToggle.classList.toggle('collapsed', isOpen);
    menuToggle.setAttribute('aria-expanded', String(!isOpen));
  });

  mobileNav?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      mobileNav.setAttribute('hidden', '');
      menuToggle?.classList.add('collapsed');
      menuToggle?.setAttribute('aria-expanded', 'false');
    });
  });

  const year = document.querySelector('[data-year]');
  if (year) {
    year.textContent = String(new Date().getFullYear());
  }

  // Delegated interactive toggler for publication abstracts and BibTeX panels
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-toggle-target]');
    if (!btn) return;

    e.preventDefault();
    const targetId = btn.getAttribute('data-toggle-target');
    const targetPanel = document.getElementById(targetId);
    if (!targetPanel) return;

    // Find other panels in the same publication item and close them
    const parent = btn.closest('.pub-body') || btn.closest('.pub-item');
    if (parent) {
      const peerBtns = parent.querySelectorAll('[data-toggle-target]');
      peerBtns.forEach((otherBtn) => {
        if (otherBtn !== btn) {
          const otherTargetId = otherBtn.getAttribute('data-toggle-target');
          const otherPanel = document.getElementById(otherTargetId);
          if (otherPanel && !otherPanel.hasAttribute('hidden')) {
            otherPanel.setAttribute('hidden', '');
            otherBtn.classList.remove('active');
            otherBtn.setAttribute('aria-expanded', 'false');
          }
        }
      });
    }

    const isHidden = targetPanel.hasAttribute('hidden');
    targetPanel.toggleAttribute('hidden', !isHidden);
    btn.classList.toggle('active', isHidden);
    btn.setAttribute('aria-expanded', String(isHidden));
  });

  // Dynamic GitHub Repositories
  const statsContainer = document.getElementById('github-stats-container');
  const reposContainer = document.getElementById('github-repos-container');

  if (statsContainer && reposContainer) {
    const langColors = {
      JavaScript: '#f1e05a',
      TypeScript: '#3178c6',
      Python: '#3572A5',
      HTML: '#e34c26',
      CSS: '#563d7c',
      Java: '#b07219',
      Ruby: '#701516',
      R: '#198ce7',
      C: '#555555',
      'C++': '#f34b7d',
})();
