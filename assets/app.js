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
 document.querySelectorAll('.page-finder, .site-search, .table-filter').forEach(finder=>{
  finder.dispatchEvent(new Event('languagechange'));
 });
}
setLanguage(languageFromUrl());
document.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>setLanguage(b.dataset.lang,'push')));
window.addEventListener('popstate',()=>{setLanguage(languageFromUrl());openHash();});
document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
const search=document.getElementById('nav-search');if(search)search.addEventListener('input',()=>{const q=search.value.toLowerCase().trim();document.querySelectorAll('.month-links a').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q))});
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
