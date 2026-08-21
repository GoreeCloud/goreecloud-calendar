const app = document.querySelector('[data-calendar-app]');
const stage = document.querySelector('[data-calendar-stage]');
const periodLabel = document.querySelector('[data-period-label]');
const viewLabel = document.querySelector('[data-view-label]');
const statusBanner = document.querySelector('[data-status]');
const dialog = document.querySelector('[data-event-dialog]');
const form = document.querySelector('[data-event-form]');

const state = {
  view: 'month',
  anchor: new Date(),
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
};

function announce(message, isError = false) {
  statusBanner.hidden = !message;
  statusBanner.textContent = message;
  statusBanner.dataset.kind = isError ? 'error' : 'info';
}

function formatPeriod() {
  const options = state.view === 'day'
    ? { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }
    : { month: 'long', year: 'numeric' };
  periodLabel.textContent = new Intl.DateTimeFormat(undefined, options).format(state.anchor);
  viewLabel.textContent = `${state.view[0].toUpperCase()}${state.view.slice(1)} view`;
}

function eventCard(event) {
  const article = document.createElement('article');
  article.className = 'event-card';
  const title = document.createElement('h3');
  title.textContent = event.title;
  const time = document.createElement('p');
  time.className = 'event-time';
  const starts = new Date(event.starts_at);
  const ends = new Date(event.ends_at);
  time.textContent = `${starts.toLocaleString()} – ${ends.toLocaleString()}`;
  article.append(title, time);
  if (event.location) {
    const location = document.createElement('p');
    location.textContent = event.location;
    article.append(location);
  }
  return article;
}

function render(payload) {
  stage.replaceChildren();
  stage.setAttribute('aria-busy', 'false');
  if (!payload.events?.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'No events in this period.';
    stage.append(empty);
    return;
  }
  const list = document.createElement('div');
  list.className = `event-list view-${state.view}`;
  for (const event of payload.events) list.append(eventCard(event));
  stage.append(list);
}

async function loadEvents() {
  formatPeriod();
  stage.setAttribute('aria-busy', 'true');
  announce('');
  const anchor = state.anchor.toISOString().slice(0, 10);
  const params = new URLSearchParams({ view: state.view, anchor, timezone: state.timezone });
  try {
    const response = await fetch(`/api/v1/calendar/events?${params}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    if (!response.ok) throw new Error(`Calendar request failed with HTTP ${response.status}`);
    const payload = await response.json();
    if (payload.schema !== 'goreecloud.calendar.events.v1' || payload.version !== 1) {
      throw new Error('Calendar returned an unsupported response contract.');
    }
    render(payload);
  } catch (error) {
    stage.setAttribute('aria-busy', 'false');
    stage.innerHTML = '<p class="empty-state">Calendar data is temporarily unavailable.</p>';
    announce(error.message || 'Calendar data is temporarily unavailable.', true);
  }
}

function shiftAnchor(direction) {
  const next = new Date(state.anchor);
  if (state.view === 'month') next.setMonth(next.getMonth() + direction);
  else if (state.view === 'week') next.setDate(next.getDate() + 7 * direction);
  else next.setDate(next.getDate() + direction);
  state.anchor = next;
  loadEvents();
}

async function createEvent(data) {
  const response = await fetch('/api/v1/calendar/events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`Event creation failed with HTTP ${response.status}`);
}

app.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.view) {
    state.view = button.dataset.view;
    document.querySelectorAll('[data-view]').forEach((item) => {
      item.setAttribute('aria-pressed', String(item === button));
    });
    loadEvents();
  } else if (button.dataset.action === 'today') {
    state.anchor = new Date();
    loadEvents();
  } else if (button.dataset.action === 'previous') shiftAnchor(-1);
  else if (button.dataset.action === 'next') shiftAnchor(1);
  else if (button.dataset.action === 'new-event') dialog.showModal();
  else if (button.dataset.action === 'close-dialog') dialog.close();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await createEvent(data);
    dialog.close();
    form.reset();
    announce('Event created.');
    await loadEvents();
  } catch (error) {
    announce(error.message || 'Event could not be created.', true);
  }
});

loadEvents();
