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
})();
