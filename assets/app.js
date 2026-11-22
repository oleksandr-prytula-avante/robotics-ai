(()=>{'use strict';
const scriptUrl = document.currentScript?.src;
function languageFromUrl(){
 const lang=new URLSearchParams(location.search).get('lang');
 return ['en','ru'].includes(lang)?lang:'en';
}
function setLanguage(lang,historyMode='replace'){
 if(!['en','ru'].includes(lang))lang='en';
 const currentUrl=new URL(location.href);
 currentUrl.searchParams.set('lang',lang);
 if(currentUrl.href!==location.href){
  try{window.history[historyMode+'State'](null,'',currentUrl.href)}catch(e){
   // Some file:// viewers restrict History API updates; navigation still preserves the choice.
   if(historyMode==='push'){location.href=currentUrl.href;return;}
  }
 }
 document.documentElement.lang=lang;
 document.querySelectorAll('[data-lang]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.lang===lang)));
 document.title=document.documentElement.dataset[lang+'Title']||document.title;
 // Keep local page links shareable, including links opened in a new tab.
 document.querySelectorAll('a[href]').forEach(a=>{
  const raw=a.getAttribute('href');
  if(!raw||raw.startsWith('#')||a.hasAttribute('download'))return;
  let url;try{url=new URL(raw,location.href)}catch(e){return;}
  if(url.origin!==location.origin||url.protocol!==location.protocol||!/(?:\.html|\/)$/i.test(url.pathname))return;
  url.searchParams.set('lang',lang);
  a.setAttribute('href',url.href);
 });
 document.querySelectorAll('.page-finder, .site-search, .table-filter, .study-progress').forEach(finder=>{
  finder.dispatchEvent(new Event('languagechange'));
 });
}
setLanguage(languageFromUrl());
document.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>setLanguage(b.dataset.lang,'push')));
window.addEventListener('popstate',()=>{setLanguage(languageFromUrl());openHash();});
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
function openHash() {
 let id;
 try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
 const target = document.getElementById(id);
 for (let detail = target?.closest?.('details'); detail; detail = detail.parentElement.closest('details')) {
  detail.open = true;
 }
 if (target?.tagName === 'DETAILS') target.open = true;
}
openHash();window.addEventListener('hashchange',openHash);

const roadmap = document.getElementById('timeline');
if (roadmap?.querySelector('[data-roadmap-controls]')) {
 const controls = roadmap.querySelector('[data-roadmap-controls]');
 const filters = [...controls.querySelectorAll('[data-track-filter]')];
 const pickers = [...controls.querySelectorAll('[data-stage-picker]')];
 const bars = [...roadmap.querySelectorAll('[data-timeline-stage]')];
 const tracks = [...roadmap.querySelectorAll('[data-roadmap-track]')];
 const details = [...roadmap.querySelectorAll('[data-stage-detail]')];
 let selected = pickers[0].value;

 function showStage(key, reveal = false) {
  selected = key;
  let active;
  details.forEach(card => {
   card.hidden = card.dataset.stageDetail !== key;
   if (!card.hidden) active = card;
  });
  pickers.forEach(picker => { picker.value = key; });
  bars.forEach(bar => {
   if (bar.dataset.timelineStage === key) bar.setAttribute('aria-current', 'true');
   else bar.removeAttribute('aria-current');
  });
  if (reveal) {
   active.querySelector('h3').setAttribute('tabindex', '-1');
   active.querySelector('h3').focus({ preventScroll: true });
   active.scrollIntoView({ block: 'nearest' });
  }
 }

 function filterTracks(key) {
  filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.trackFilter === key)));
  tracks.forEach(row => { row.hidden = key !== 'all' && row.dataset.roadmapTrack !== key; });
  pickers.forEach(picker => {
   [...picker.options].forEach(option => {
    option.hidden = option.disabled = key !== 'all' && option.dataset.track !== key;
   });
  });
  const options = [...pickers[0].options];
  showStage(options.some(option => option.value === selected && !option.disabled)
   ? selected : options.find(option => !option.disabled).value);
 }

 filters.forEach(button => button.addEventListener('click', () => filterTracks(button.dataset.trackFilter)));
 pickers.forEach(picker => picker.addEventListener('change', () => {
  showStage(picker.value, window.matchMedia('(max-width: 720px)').matches);
 }));
 bars.forEach(bar => {
  bar.setAttribute('aria-controls', 'roadmap-stage-details');
  bar.addEventListener('click', event => {
   if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
   event.preventDefault();
   showStage(bar.dataset.timelineStage, true);
  });
 });
 controls.hidden = false;
 showStage(selected);
}

// Search headings while keeping the full content and its links in place.
const main = document.querySelector?.('main');
const pageTitle = main?.querySelector('h1');
const entries = main ? [...main.querySelectorAll('section[id], article[id], details[id], h2[id], h3[id]')]
 .filter(section => !section.closest('#timeline, #growth-timeline, #timeline-summary'))
 .map(section => ({
  id: section.id,
  heading: section.matches('h2, h3') ? section : section.querySelector('h2, h3, summary'),
 }))
 .filter(entry => entry.heading) : [];
if (pageTitle && entries.length > 0) {
 const finder = document.createElement('details');
 finder.className = 'page-finder';
 finder.innerHTML = '<summary><span lang="ru">Найти раздел на странице</span><span lang="en">Find a section on this page</span></summary>'
  + '<div><label for="page-finder-input" class="visually-hidden"><span lang="ru">Название или код раздела</span>'
  + '<span lang="en">Section title or code</span></label><input id="page-finder-input" type="search">'
  + '<p class="page-finder-status" aria-live="polite"></p><ul class="page-finder-results"></ul></div>';
 (pageTitle.closest('.hero') || pageTitle).after(finder);
 const field = finder.querySelector('input');
 const results = finder.querySelector('ul');
 const status = finder.querySelector('.page-finder-status');
 function findSections() {
  const lang = document.documentElement.lang;
  const ru = lang === 'ru';
  field.placeholder = ru ? 'Название или код раздела' : 'Section title or code';
  const query = field.value.toLocaleLowerCase().trim().split(/\s+/);
  const matches = entries.flatMap(({ id, heading }) => {
   const label = (heading.querySelector(`[lang="${lang}"]`) || heading).textContent.trim();
   const searchable = `${id} ${heading.textContent}`.toLocaleLowerCase();
   return query.every(term => searchable.includes(term)) ? [{ id, label }] : [];
  });
  status.textContent = matches.length
   ? (ru ? `Разделов: ${matches.length}` : `Sections: ${matches.length}`)
   : (ru ? 'Разделы не найдены' : 'No matching sections');
  results.replaceChildren(...matches.map(({ id, label }) => {
   const item = document.createElement('li');
   const link = document.createElement('a');
   link.href = '#' + encodeURIComponent(id);
   link.textContent = label;
   item.append(link);
   return item;
  }));
 }
 finder.addEventListener('languagechange', findSections);
 field.addEventListener('input', findSections);
 results.addEventListener('click', event => {
  const link = event.target.closest('a');
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
  for (let detail = target.closest('details'); detail; detail = detail.parentElement.closest('details')) {
   detail.open = true;
  }
  finder.open = false;
  if (link.hash === location.hash) target.scrollIntoView();
 });
 findSections();
}

function bilingual(ru, en) {
 const text = document.createDocumentFragment();
 for (const [lang, value] of [['ru', ru], ['en', en]]) {
  const span = document.createElement('span');
  span.lang = lang;
  span.textContent = value;
  text.append(span);
 }
 return text;
}

const sidebar = document.querySelector?.('.sidebar');
if (sidebar) {
 const toggle = document.createElement('button');
 toggle.type = 'button';
 toggle.className = 'mobile-menu-toggle';
 toggle.append(bilingual('Разделы сайта', 'Site sections'));
 sidebar.id ||= 'site-sidebar';
 toggle.setAttribute('aria-controls', sidebar.id);
 toggle.setAttribute('aria-expanded', 'false');
 toggle.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') === 'true';
  toggle.setAttribute('aria-expanded', String(!open));
 });
 sidebar.before(toggle);
}

if (scriptUrl && pageTitle) {
 const root = new URL('../', scriptUrl);
 const current = new URL(location.href);
 const page = current.pathname.slice(root.pathname.length);
 const month = /^months\/\d{4}-\d{2}\.html$/.test(page);
 const storagePrefix = `robotics-ai:study:${root.pathname}:`;
 const memory = new Map();
 let storageAvailable = true;

 function readProgress(key) {
  if (memory.has(key)) return memory.get(key);
  try { return localStorage.getItem(storagePrefix + key); }
  catch { storageAvailable = false; return null; }
 }

 function saveProgress(key, value) {
  try { localStorage.setItem(storagePrefix + key, value); }
  catch { storageAvailable = false; memory.set(key, value); }
 }

 function savedTask() {
  try { return JSON.parse(readProgress('resume')); } catch { return null; }
 }

 const insertionPoint = pageTitle.closest('.hero') || pageTitle;
 if (month) {
  const tasks = [...main.querySelectorAll('td [data-task][data-part-minutes]')];
  if (tasks.length) {
   const toolbar = document.createElement('section');
   toolbar.className = 'study-progress';
   toolbar.innerHTML = '<h2 id="study-progress-title"></h2><p class="study-status" aria-live="polite"></p>'
    + '<progress aria-labelledby="study-progress-title"></progress><div class="study-actions">'
    + '<a class="button study-next"></a><label class="study-check"><input type="checkbox"></label></div>'
    + '<label class="study-search"><input type="search"></label>'
    + '<p class="small study-storage"></p>';
   toolbar.setAttribute('aria-labelledby', 'study-progress-title');
   toolbar.querySelector('h2').append(bilingual('Прогресс за месяц', 'Monthly progress'));
   toolbar.querySelector('.study-check').append(bilingual('Только незавершённое', 'Show incomplete only'));
   const status = toolbar.querySelector('.study-status');
   const progress = toolbar.querySelector('progress');
   const next = toolbar.querySelector('.study-next');
   const filter = toolbar.querySelector('input[type="checkbox"]');
   const search = toolbar.querySelector('input[type="search"]');
   const storageNote = toolbar.querySelector('.study-storage');
   const parts = tasks.map(task => {
    const row = task.closest('tr');
    const table = task.closest('.table-wrap');
    const week = table.previousElementSibling?.previousElementSibling?.id;
    table.classList.add('study-table');
    const id = `study-${week}-${task.dataset.task}`;
    const key = `${page}#${id}`;
    const label = document.createElement('label');
    label.className = 'study-check study-task-check';
    const check = document.createElement('input');
    check.type = 'checkbox';
    const titles = {};
    for (const title of task.querySelectorAll(':scope > span[lang]')) {
     title.id = `${id}-${title.lang}`;
     titles[title.lang] = title.textContent;
    }
    function remember() {
     saveProgress('resume', JSON.stringify({ page, id, titles }));
    }
    check.checked = readProgress(key) === 'done';
    label.append(check, bilingual('Часть выполнена', 'Part complete'));
    for (const word of label.querySelectorAll('[lang]')) word.id = `${id}-complete-${word.lang}`;
    const bookmark = document.createElement('button');
    bookmark.type = 'button';
    bookmark.className = 'study-check';
    bookmark.append(bilingual('Продолжить отсюда', 'Resume here'));
    bookmark.addEventListener('click', () => {
     remember();
     render();
    });
    const actions = document.createElement('div');
    actions.className = 'study-actions';
    actions.append(label, bookmark);
    task.append(actions);
    row.id = id;
    check.addEventListener('change', () => {
     saveProgress(key, check.checked ? 'done' : 'pending');
     if (filter.checked && check.checked) filter.focus();
     render();
    });
    return { row, check, id, key, bookmark, remember, minutes: Number(task.dataset.partMinutes),
     text: row.textContent.toLocaleLowerCase() };
   });
   const plannedMinutes = parts.reduce((sum, part) => sum + part.minutes, 0);
   next.append(bilingual('К следующему заданию ↓', 'Go to next task ↓'));
   function render() {
    const ru = document.documentElement.lang === 'ru';
    const done = parts.filter(part => part.check.checked);
    const minutes = done.reduce((sum, part) => sum + part.minutes, 0);
    const saved = savedTask();
    const terms = search.value.trim().toLocaleLowerCase().split(/\s+/);
    let visible = 0;
    for (const { row, check, id, text, bookmark } of parts) {
     const matches = terms.every(term => text.includes(term));
     row.hidden = !matches || (filter.checked && check.checked);
     if (!row.hidden) visible++;
     row.classList.toggle('study-complete', check.checked);
     const lang = ru ? 'ru' : 'en';
     check.setAttribute('aria-labelledby', `${id}-complete-${lang} ${id}-${lang}`);
     const marked = saved?.page === page && saved.id === id;
     bookmark.setAttribute('aria-pressed', String(marked));
    }
    const pending = parts.find(part => !part.check.checked && !part.row.hidden);
    progress.max = plannedMinutes;
    progress.value = minutes;
    const duration = value => `${Math.floor(value / 60)} ${ru ? 'ч' : 'h'} ${value % 60} ${ru ? 'мин' : 'min'}`;
    status.textContent = ru
     ? `Выполнено ${done.length} из ${parts.length} частей · ${duration(minutes)} из ${duration(plannedMinutes)} по плану`
     : `${done.length} of ${parts.length} parts complete · ${duration(minutes)} of ${duration(plannedMinutes)} planned`;
    if (visible !== parts.length) status.textContent += ru ? ` · Показано ${visible}` : ` · ${visible} shown`;
    search.placeholder = ru ? 'Поиск по заданиям месяца' : 'Search this month’s tasks';
    search.setAttribute('aria-label', search.placeholder);
    next.hidden = !pending;
    if (pending) next.href = `#${pending.id}`;
    storageNote.textContent = storageAvailable
     ? (ru ? 'Отметки сохраняются в этом браузере.' : 'Progress is saved in this browser.')
     : (ru ? 'Хранилище недоступно. Новые отметки действуют до перезагрузки.' : 'Storage is unavailable. New changes last until reload.');
   }
   filter.addEventListener('change', render);
   search.addEventListener('input', render);
   toolbar.addEventListener('languagechange', render);
   window.addEventListener('storage', event => {
    if (event.key !== null && !event.key.startsWith(storagePrefix)) return;
    parts.forEach(({ check, key }) => { check.checked = readProgress(key) === 'done'; });
    render();
   });
   next.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const pending = parts.find(part => !part.check.checked && !part.row.hidden);
    pending?.remember();
    render();
    pending?.check.focus({ preventScroll: true });
   });
   insertionPoint.after(toolbar);
   render();
   const target = parts.find(part => `#${part.id}` === location.hash);
   if (target) window.requestAnimationFrame(() => target.row.scrollIntoView());
  }
 } else if (page === '' || page === 'index.html') {
  const resume = document.createElement('div');
  resume.className = 'study-progress';
  const link = document.createElement('a');
  link.className = 'button';
  link.append(bilingual('Продолжить обучение', 'Resume learning'));
  const title = document.createElement('span');
  title.className = 'study-resume-month';
  function updateResume() {
   const saved = savedTask();
   const lastMonth = saved?.page || readProgress('last-month');
   const monthLink = [...(sidebar?.querySelectorAll('.month-links a') || [])].find(link =>
    new URL(link.href).pathname === root.pathname + lastMonth);
   resume.hidden = !monthLink;
   if (!monthLink) return;
   const url = new URL(monthLink.href);
   url.searchParams.set('lang', document.documentElement.lang);
   url.hash = /^study-week-\d+-[\w.]+$/.test(saved?.id) ? saved.id : 'study-progress-title';
   link.href = url.href;
   title.replaceChildren();
   if (saved?.titles) title.append(bilingual(saved.titles.ru, saved.titles.en));
   else for (const name of monthLink.querySelectorAll(':scope > span[lang]')) title.append(name.cloneNode(true));
  }
  resume.append(link, title);
  resume.addEventListener('languagechange', updateResume);
  window.addEventListener('pageshow', updateResume);
  window.addEventListener('storage', updateResume);
  insertionPoint.after(resume);
  updateResume();
 }
}

if (main) {
 const folds = [...main.querySelectorAll('details:not(.page-finder)')];
 if (folds.length > 1 && !main.querySelector('#expand-pages')) {
  const controls = document.createElement('div');
  controls.className = 'fold-controls';
  for (const [open, ru, en] of [[true, 'Раскрыть всё', 'Expand all'], [false, 'Свернуть всё', 'Collapse all']]) {
   const button = document.createElement('button');
   button.type = 'button';
   button.append(bilingual(ru, en));
   button.addEventListener('click', () => { folds.forEach(detail => { detail.open = open; }); });
   controls.append(button);
  }
  const finder = main.querySelector('.page-finder');
  (finder || pageTitle)?.after(controls);
 }
 main.querySelectorAll('.table-wrap > table').forEach(table => {
  if (table.querySelector('.study-task-check')) return;
  const rows = [...table.tBodies].flatMap(body => [...body.rows]).filter(row => row.querySelector('td'));
  if (rows.length < 12 || rows.some(row => row.querySelector('[colspan], [rowspan]'))) return;
  const form = document.createElement('div');
  form.className = 'table-filter';
  const field = document.createElement('input');
  field.type = 'search';
  const label = document.createElement('label');
  label.append(bilingual('Поиск по строкам таблицы', 'Search table rows'), field);
  const status = document.createElement('span');
  status.setAttribute('aria-live', 'polite');
  form.append(label, status);
  table.parentElement.before(form);
  const text = rows.map(row => row.textContent.toLocaleLowerCase());
  function filterRows() {
   const isRussian = document.documentElement.lang === 'ru';
   const terms = field.value.trim().toLocaleLowerCase().split(/\s+/);
   let count = 0;
   rows.forEach((row, index) => {
    row.hidden = !terms.every(term => text[index].includes(term));
    if (!row.hidden) count++;
   });
   status.textContent = isRussian ? `${count} из ${rows.length}` : `${count} of ${rows.length}`;
  }
  field.addEventListener('input', filterRows);
  form.addEventListener('languagechange', filterRows);
  filterRows();
 });
}

const topActions = document.querySelector?.('.topbar .top-actions, .topbar .lang-switch');
if (scriptUrl && topActions) {
 const trigger = document.createElement('button');
 trigger.type = 'button';
 trigger.className = 'site-search-trigger';
 trigger.append(bilingual('Поиск', 'Search'));
 const dialog = document.createElement('dialog');
 dialog.className = 'site-search';
 dialog.setAttribute('aria-labelledby', 'site-search-title');
 dialog.innerHTML = '<header><h2 id="site-search-title"></h2><button type="button" class="site-search-close"></button></header>'
  + '<label class="visually-hidden" for="site-search-query"></label><input id="site-search-query" type="search" autofocus>'
  + '<p class="site-search-status" aria-live="polite"></p><ul class="site-search-results"></ul>';
 dialog.querySelector('h2').append(bilingual('Поиск по сайту', 'Search the site'));
 dialog.querySelector('label').append(bilingual('Поисковый запрос', 'Search query'));
 dialog.querySelector('button').append(bilingual('Закрыть', 'Close'));
 if (topActions.classList.contains('top-actions')) {
  topActions.prepend(trigger);
 } else {
  const group = document.createElement('div');
  group.className = 'top-actions top-search-actions';
  topActions.before(group);
  group.append(trigger, topActions);
 }
 document.body.append(dialog);
 const field = dialog.querySelector('input');
 const status = dialog.querySelector('p');
 const resultList = dialog.querySelector('ul');
 const root = new URL('../', scriptUrl);
 let loadIndex;

 function searchSite() {
  const lang = document.documentElement.lang;
  const ru = lang === 'ru';
  field.placeholder = ru ? 'Например: M19, MoveIt, ESP32' : 'For example: M19, MoveIt, ESP32';
  const index = window.roboticsSearchIndex;
  if (!index) return;
  const query = field.value.trim().toLocaleLowerCase();
  const terms = query.split(/\s+/);
  const matches = index.filter(([path, russian, english]) => {
   if (!query) return !path.includes('#') && !path.includes('/');
   const searchable = `${decodeURIComponent(path)} ${russian} ${english}`.toLocaleLowerCase();
   return terms.every(term => searchable.includes(term));
  });
  const featured = matches.slice(0, 30);
  status.textContent = matches.length
   ? (ru ? `Показано ${featured.length} из ${matches.length}` : `Showing ${featured.length} of ${matches.length}`)
   : (ru ? 'Совпадений нет' : 'No matches');
  const pageTitles = new Map(index.filter(([path]) => !path.includes('#'))
   .map(([path, russian, english]) => [path, ru ? russian : english]));
  resultList.replaceChildren(...featured.map(([path, russian, english]) => {
   const item = document.createElement('li');
   const link = document.createElement('a');
   const url = new URL(path, root);
   url.searchParams.set('lang', lang);
   link.href = url.href;
   link.textContent = ru ? russian : english;
   if (url.hash) {
    const context = document.createElement('small');
    context.textContent = pageTitles.get(path.split('#')[0]);
    link.append(context);
   }
   item.append(link);
   return item;
  }));
 }

 async function openSearch() {
  if (!dialog.open) dialog.showModal();
  field.focus();
  if (!loadIndex) {
   loadIndex = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = new URL('assets/search-index.js', root).href;
    script.addEventListener('load', resolve, { once: true });
    script.addEventListener('error', () => { script.remove(); reject(); }, { once: true });
    document.head.append(script);
   });
  }
  const ru = document.documentElement.lang === 'ru';
  if (!window.roboticsSearchIndex) status.textContent = ru ? 'Загружаю разделы…' : 'Loading sections…';
  try {
   await loadIndex;
   searchSite();
  } catch {
   loadIndex = null;
   status.textContent = ru ? 'Не удалось загрузить поиск' : 'Could not load search';
  }
 }

 trigger.addEventListener('click', openSearch);
 dialog.querySelector('button').addEventListener('click', () => dialog.close());
 resultList.addEventListener('click', event => {
  if (event.target.closest('a') && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) dialog.close();
 });
 dialog.addEventListener('languagechange', searchSite);
 field.addEventListener('input', searchSite);
 document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k' && !event.altKey) {
   event.preventDefault();
   openSearch();
  }
 });
}
})();
