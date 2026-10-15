/* Progressive enhancement: the original content remains readable without JS. */
const menu = document.querySelector('.menu');
const nav = document.querySelector('#navigation');
const languages = document.querySelector('.languages');
const mobileNavigation = window.matchMedia('(max-width:760px)');
let menuAnimation;
function setMenu(opened) {
  if (!menu || !nav) return;
  const wasOpen = nav.classList.contains('is-open');
  menuAnimation?.cancel();
  menu.setAttribute('aria-expanded', String(opened));
  menu.setAttribute('aria-label', opened ? 'Fermer le menu' : 'Ouvrir le menu');
  nav.inert = mobileNavigation.matches && !opened;
  if (opened) nav.classList.add('is-open');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  if (!mobileNavigation.matches || reducedMotion || !nav.animate || (!opened && !wasOpen)) {
    if (!opened) nav.classList.remove('is-open');
    return;
  }
  const animation = nav.animate(opened
    ? [{opacity:0,transform:'translateY(-7px)'},{opacity:1,transform:'translateY(0)'}]
    : [{opacity:1,transform:'translateY(0)'},{opacity:0,transform:'translateY(-5px)'}],
    {duration:opened ? 240 : 170,easing:'cubic-bezier(.25,1,.5,1)'});
  menuAnimation = animation;
  animation.finished.then(() => {
    if (menuAnimation === animation && !opened) nav.classList.remove('is-open');
  }).catch(() => {});
}
function closeMenu() {
  setMenu(false);
}
menu?.addEventListener('click', event => {
  const opened = menu.getAttribute('aria-expanded') !== 'true';
  setMenu(opened);
  if (opened && event.detail === 0) nav?.querySelector('a')?.focus({preventScroll:true});
});
if (nav) nav.inert = mobileNavigation.matches;
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (menu?.getAttribute('aria-expanded') === 'true') { closeMenu(); menu.focus(); }
    if (languages?.open) { languages.open = false; languages.querySelector('summary').focus(); }
  }
});
document.addEventListener('click', event => {
  if (languages && !languages.contains(event.target)) languages.open = false;
});
nav?.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
window.matchMedia('(min-width:761px)').addEventListener('change', closeMenu);

// Existing event anchors reveal their archive panel when followed directly.
function revealArchiveAnchor() {
  if (!location.hash) return;
  let identifier;
  try { identifier = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = document.getElementById(identifier);
  if (!target || !target.closest('.archive-event')) return;
  for (let parent = target.parentElement; parent; parent = parent.parentElement) {
    if (parent instanceof HTMLDetailsElement) parent.open = true;
  }
  target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange',revealArchiveAnchor);
if (location.hash) requestAnimationFrame(revealArchiveAnchor);

const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
const filterForm = document.querySelector('.filters, .directory-search');
if (filterForm) {
  const entries = [...document.querySelectorAll('[data-catalog-entry], [data-directory-entry]')];
  const count = document.querySelector('.result-count');
  const empty = document.querySelector('.empty-results');
  const prepared = entries.map(element => ({ element, text: normalize(element.dataset.search || element.textContent) }));
  const batches = [...document.querySelectorAll('[data-catalog-batch]')];
  function filter() {
    const values = new FormData(filterForm);
    const terms = normalize(String(values.get('q') || '')).split(/\s+/).filter(Boolean);
    let visible = 0;
    for (const item of prepared) {
      const matchesText = terms.every(term => item.text.includes(term));
      const matchesFields = ['type', 'status', 'wood'].every(field => !values.get(field) || item.element.dataset[field] === values.get(field));
      item.element.hidden = !matchesText || !matchesFields;
      if (!item.element.hidden) visible++;
    }
    count.textContent = `${visible} / ${entries.length} ${filterForm.classList.contains('directory-search') ? 'luthiers' : 'instruments'}`;
    empty.hidden = visible !== 0;
    for (const batch of batches) batch.hidden = !batch.querySelector('[data-catalog-entry]:not([hidden])');
    // Filtering preserves the generated order, with available instruments first.
    if (filterForm.classList.contains('filters')) {
      const params = new URLSearchParams(location.search);
      for (const [key, value] of values) value ? params.set(key, value) : params.delete(key);
      const query = params.toString();
      history.replaceState(null, '', location.pathname + (query ? '?' + query : '') + location.hash);
    }
  }
  const initial = new URLSearchParams(location.search);
  for (const [key, value] of initial) {
    const input = filterForm.elements.namedItem(key);
    if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement) input.value = value;
  }
  filterForm.addEventListener('submit', event => { event.preventDefault(); filter(); });
  filterForm.addEventListener('input', filter);
  filterForm.addEventListener('change', filter);
  filterForm.addEventListener('reset', event => {
    event.preventDefault();
    for (const control of filterForm.querySelectorAll('input, select')) control.value = '';
    filter();
  });
  filter();
}

// Unlinked editorial photographs receive the same accessible zoom control.
for (const image of document.querySelectorAll('.rich-text img')) {
  if (image.closest('a, button') || image.getAttribute('src')?.includes('/objects/')) continue;
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'gallery-photo inline-photo';
  button.dataset.photo = image.getAttribute('src');
  button.dataset.caption = image.alt;
  button.setAttribute('aria-label', `Agrandir : ${image.alt}`);
  image.replaceWith(button); button.append(image);
}
const photoButtons = [...document.querySelectorAll('[data-photo]')];
const dialog = document.querySelector('.photo-dialog');
let selected = 0;
let lastFocus = null;
function showPhoto(index) {
  selected = (index + photoButtons.length) % photoButtons.length;
  const button = photoButtons[selected];
  const image = dialog.querySelector('.photo-large');
  image.src = button.dataset.photo;
  image.alt = button.dataset.caption || '';
  dialog.querySelector('.photo-caption').textContent = image.alt;
  dialog.querySelector('.photo-number').textContent = `${selected + 1} / ${photoButtons.length}`;
}
photoButtons.forEach((button, index) => button.addEventListener('click', () => {
  if (!dialog) return;
  lastFocus = button; showPhoto(index); dialog.showModal();
}));
dialog?.querySelector('[data-close-photo]').addEventListener('click', () => dialog.close());
dialog?.querySelector('[data-prev-photo]').addEventListener('click', () => showPhoto(selected - 1));
dialog?.querySelector('[data-next-photo]').addEventListener('click', () => showPhoto(selected + 1));
dialog?.addEventListener('keydown', event => {
  if (event.key === 'ArrowRight') { event.preventDefault(); showPhoto(selected + 1); }
  if (event.key === 'ArrowLeft') { event.preventDefault(); showPhoto(selected - 1); }
});
dialog?.addEventListener('close', () => lastFocus?.focus());
dialog?.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
});
