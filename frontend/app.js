const state = {
  session: null,
  calendars: [],
  selected: new Set(),
  events: [],
  month: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  editing: null,
};

const $ = (id) => document.getElementById(id);

const elements = {
  loginView: $("loginView"),
  appView: $("appView"),
  loginForm: $("loginForm"),
  username: $("username"),
  password: $("password"),
  loginError: $("loginError"),
  logoutButton: $("logoutButton"),
  userLabel: $("userLabel"),
  calendarList: $("calendarList"),
  calendarGrid: $("calendarGrid"),
  monthTitle: $("monthTitle"),
  prevButton: $("prevButton"),
  nextButton: $("nextButton"),
  todayButton: $("todayButton"),
  refreshButton: $("refreshButton"),
  newEventButton: $("newEventButton"),
  syncState: $("syncState"),
  emptyState: $("emptyState"),
  themeButton: $("themeButton"),
  eventDialog: $("eventDialog"),
  eventForm: $("eventForm"),
  dialogTitle: $("dialogTitle"),
  eventHref: $("eventHref"),
  eventEtag: $("eventEtag"),
  eventCalendar: $("eventCalendar"),
  eventSummary: $("eventSummary"),
  eventAllDay: $("eventAllDay"),
  eventStart: $("eventStart"),
  eventEnd: $("eventEnd"),
  eventLocation: $("eventLocation"),
  eventDescription: $("eventDescription"),
  eventWarning: $("eventWarning"),
  eventError: $("eventError"),
  saveEventButton: $("saveEventButton"),
  deleteEventButton: $("deleteEventButton"),
  closeDialogButton: $("closeDialogButton"),
  cancelEventButton: $("cancelEventButton"),
  toast: $("toast"),
};

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (state.session?.csrf_token && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase())) {
    headers["X-CSRF-Token"] = state.session.csrf_token;
  }

  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers,
  });

  if (response.status === 401) {
    showLogin();
    throw new Error("Your session has expired. Sign in again.");
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

function showLogin() {
  state.session = null;
  state.calendars = [];
  state.selected.clear();
  state.events = [];
  elements.appView.classList.add("hidden");
  elements.loginView.classList.remove("hidden");
  elements.password.value = "";
}

function showApp() {
  elements.loginView.classList.add("hidden");
  elements.appView.classList.remove("hidden");
  elements.userLabel.textContent = state.session.username;
  elements.newEventButton.disabled = !state.session.write_enabled;
  elements.newEventButton.title = state.session.write_enabled
    ? "Create an event"
    : "CalDAV writes are disabled by the safety gate";
}

async function restoreSession() {
  try {
    state.session = await api("/api/auth/me");
    showApp();
    await refreshAll();
  } catch (_) {
    showLogin();
  }
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginError.textContent = "";
  const button = elements.loginForm.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    state.session = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: elements.username.value,
        password: elements.password.value,
      }),
    });
    elements.password.value = "";
    showApp();
    await refreshAll();
  } catch (error) {
    elements.loginError.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

elements.logoutButton.addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (_) {}
  showLogin();
});

function colorClass(index) {
  return `calendar-color-${Math.max(index, 0) % 6}`;
}

async function refreshAll() {
  elements.syncState.textContent = "Syncing";
  try {
    state.calendars = await api("/api/calendars");
    if (state.selected.size === 0) {
      state.calendars.forEach((calendar) => state.selected.add(calendar.href));
    } else {
      const valid = new Set(state.calendars.map((calendar) => calendar.href));
      state.selected = new Set([...state.selected].filter((href) => valid.has(href)));
    }
    renderCalendarList();
    populateCalendarSelect();
    await loadEvents();
    elements.syncState.textContent = "Connected";
  } catch (error) {
    elements.syncState.textContent = "Connection issue";
    toast(error.message);
  }
}

function renderCalendarList() {
  elements.calendarList.replaceChildren();
  state.calendars.forEach((calendar, index) => {
    const label = document.createElement("label");
    label.className = "calendar-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(calendar.href);
    checkbox.addEventListener("change", async () => {
      if (checkbox.checked) state.selected.add(calendar.href);
      else state.selected.delete(calendar.href);
      await loadEvents();
    });
    const dot = document.createElement("span");
    dot.className = "calendar-dot";
    dot.classList.add(colorClass(index));
    const name = document.createElement("span");
    name.textContent = calendar.display_name;
    label.append(checkbox, dot, name);
    elements.calendarList.append(label);
  });
}

function populateCalendarSelect() {
  elements.eventCalendar.replaceChildren();
  state.calendars.forEach((calendar) => {
    const option = document.createElement("option");
    option.value = calendar.href;
    option.textContent = calendar.display_name;
    elements.eventCalendar.append(option);
  });
}

function monthGridRange() {
  const first = new Date(state.month.getFullYear(), state.month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(start.getDate() - start.getDay());
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 42);
  return { start, end };
}

async function loadEvents() {
  state.events = [];
  const { start, end } = monthGridRange();
  const selected = state.calendars.filter((calendar) => state.selected.has(calendar.href));
  try {
    const groups = await Promise.all(
      selected.map((calendar) =>
        api(`/api/events?calendar_href=${encodeURIComponent(calendar.href)}&start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`)
      )
    );
    state.events = groups.flat();
    renderMonth();
  } catch (error) {
    renderMonth();
    toast(error.message);
  }
}

function renderMonth() {
  elements.monthTitle.textContent = state.month.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
  const { start } = monthGridRange();
  const todayKey = dateKey(new Date());
  elements.calendarGrid.replaceChildren();

  for (let i = 0; i < 42; i += 1) {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "day-cell";
    cell.setAttribute("role", "gridcell");
    cell.dataset.date = dateKey(day);
    if (day.getMonth() !== state.month.getMonth()) cell.classList.add("outside-month");
    if (dateKey(day) === todayKey) cell.classList.add("today");

    const number = document.createElement("span");
    number.className = "day-number";
    number.textContent = day.getDate();
    cell.append(number);

    const list = document.createElement("span");
    list.className = "event-stack";
    const dayEvents = state.events
      .filter((item) => eventTouchesDay(item, day))
      .sort((a, b) => a.start.localeCompare(b.start));

    dayEvents.slice(0, 4).forEach((item) => {
      const eventButton = document.createElement("span");
      eventButton.className = "event-chip";
      const index = state.calendars.findIndex((calendar) => calendar.href === item.calendar_href);
      eventButton.classList.add(colorClass(index));
      eventButton.textContent = `${item.recurring ? "↻ " : ""}${item.summary}`;
      eventButton.title = eventTooltip(item);
      eventButton.tabIndex = 0;
      eventButton.addEventListener("click", (clickEvent) => {
        clickEvent.stopPropagation();
        openEventDialog(item);
      });
      eventButton.addEventListener("keydown", (keyEvent) => {
        if (keyEvent.key === "Enter" || keyEvent.key === " ") {
          keyEvent.preventDefault();
          openEventDialog(item);
        }
      });
      list.append(eventButton);
    });

    if (dayEvents.length > 4) {
      const more = document.createElement("span");
      more.className = "more-events";
      more.textContent = `+${dayEvents.length - 4} more`;
      list.append(more);
    }
    cell.append(list);

    cell.addEventListener("click", () => {
      if (!state.session.write_enabled) return;
      openNewEvent(day);
    });
    elements.calendarGrid.append(cell);
  }

  elements.emptyState.classList.toggle("hidden", state.events.length !== 0);
}

function dateKey(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function eventTouchesDay(event, day) {
  const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate());
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayEnd.getDate() + 1);

  if (event.all_day) {
    const eventStart = new Date(`${event.start}T00:00:00`);
    const eventEnd = event.end
      ? new Date(`${event.end}T00:00:00`)
      : new Date(eventStart.getTime() + 86400000);
    return eventStart < dayEnd && eventEnd > dayStart;
  }

  const eventStart = new Date(event.start);
  const eventEnd = event.end ? new Date(event.end) : eventStart;
  return eventStart < dayEnd && eventEnd >= dayStart;
}

function eventTooltip(event) {
  if (event.all_day) return event.summary;
  const start = new Date(event.start).toLocaleString();
  return `${event.summary} — ${start}`;
}

function toLocalInput(iso) {
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function openNewEvent(day = new Date()) {
  state.editing = null;
  elements.dialogTitle.textContent = "New event";
  elements.eventHref.value = "";
  elements.eventEtag.value = "";
  elements.eventSummary.value = "";
  elements.eventLocation.value = "";
  elements.eventDescription.value = "";
  elements.eventAllDay.checked = false;
  const start = new Date(day);
  start.setHours(9, 0, 0, 0);
  const end = new Date(start);
  end.setHours(10);
  elements.eventStart.type = "datetime-local";
  elements.eventEnd.type = "datetime-local";
  elements.eventStart.value = toLocalInput(start.toISOString());
  elements.eventEnd.value = toLocalInput(end.toISOString());
  elements.eventCalendar.value = state.calendars[0]?.href || "";
  elements.deleteEventButton.classList.add("hidden");
  elements.eventWarning.classList.add("hidden");
  elements.eventError.textContent = "";
  elements.saveEventButton.disabled = !state.session.write_enabled;
  elements.eventDialog.showModal();
}

function openEventDialog(event) {
  state.editing = event;
  elements.dialogTitle.textContent = event.summary;
  elements.eventHref.value = event.href;
  elements.eventEtag.value = event.etag || "";
  elements.eventCalendar.value = event.calendar_href;
  elements.eventSummary.value = event.summary;
  elements.eventLocation.value = event.location || "";
  elements.eventDescription.value = event.description || "";
  elements.eventAllDay.checked = event.all_day;
  setDateInputMode(event.all_day);
  if (event.all_day) {
    elements.eventStart.value = event.start;
    elements.eventEnd.value = event.end || "";
  } else {
    elements.eventStart.value = toLocalInput(event.start);
    elements.eventEnd.value = event.end ? toLocalInput(event.end) : "";
  }

  const readOnly = !state.session.write_enabled || event.recurring;
  elements.saveEventButton.disabled = readOnly;
  elements.deleteEventButton.classList.toggle("hidden", !state.session.write_enabled || !event.etag);
  elements.eventWarning.textContent = event.recurring
    ? "Recurring-event editing is intentionally read-only in this foundation release. Deleting the series is still available when writes are enabled."
    : (!state.session.write_enabled ? "CalDAV writes are disabled by the safety gate." : "");
  elements.eventWarning.classList.toggle("hidden", !elements.eventWarning.textContent);
  elements.eventError.textContent = "";
  elements.eventDialog.showModal();
}

function setDateInputMode(allDay) {
  const startValue = elements.eventStart.value;
  const endValue = elements.eventEnd.value;
  elements.eventStart.type = allDay ? "date" : "datetime-local";
  elements.eventEnd.type = allDay ? "date" : "datetime-local";
  if (allDay) {
    if (startValue) elements.eventStart.value = startValue.slice(0, 10);
    if (endValue) elements.eventEnd.value = endValue.slice(0, 10);
  }
}

elements.eventAllDay.addEventListener("change", () => {
  setDateInputMode(elements.eventAllDay.checked);
});

function buildEventPayload() {
  const allDay = elements.eventAllDay.checked;
  const start = allDay
    ? elements.eventStart.value
    : new Date(elements.eventStart.value).toISOString();
  const end = elements.eventEnd.value
    ? (allDay ? elements.eventEnd.value : new Date(elements.eventEnd.value).toISOString())
    : null;
  return {
    calendar_href: elements.eventCalendar.value,
    summary: elements.eventSummary.value.trim(),
    description: elements.eventDescription.value,
    location: elements.eventLocation.value,
    start,
    end,
    all_day: allDay,
    etag: elements.eventEtag.value || null,
  };
}

elements.eventForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.eventError.textContent = "";
  elements.saveEventButton.disabled = true;
  try {
    const payload = buildEventPayload();
    if (state.editing) {
      await api(`/api/events?event_href=${encodeURIComponent(state.editing.href)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      toast("Event updated.");
    } else {
      await api("/api/events", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast("Event created.");
    }
    elements.eventDialog.close();
    await loadEvents();
  } catch (error) {
    elements.eventError.textContent = error.message;
  } finally {
    elements.saveEventButton.disabled = !state.session.write_enabled || Boolean(state.editing?.recurring);
  }
});

elements.deleteEventButton.addEventListener("click", async () => {
  if (!state.editing?.etag) return;
  if (!window.confirm(`Delete "${state.editing.summary}"?`)) return;
  elements.deleteEventButton.disabled = true;
  try {
    await api(`/api/events?event_href=${encodeURIComponent(state.editing.href)}&etag=${encodeURIComponent(state.editing.etag)}`, {
      method: "DELETE",
    });
    elements.eventDialog.close();
    toast("Event deleted.");
    await loadEvents();
  } catch (error) {
    elements.eventError.textContent = error.message;
  } finally {
    elements.deleteEventButton.disabled = false;
  }
});

elements.closeDialogButton.addEventListener("click", () => elements.eventDialog.close());
elements.cancelEventButton.addEventListener("click", () => elements.eventDialog.close());
elements.newEventButton.addEventListener("click", () => openNewEvent());
elements.refreshButton.addEventListener("click", refreshAll);
elements.todayButton.addEventListener("click", async () => {
  state.month = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
  await loadEvents();
});
elements.prevButton.addEventListener("click", async () => {
  state.month = new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1);
  await loadEvents();
});
elements.nextButton.addEventListener("click", async () => {
  state.month = new Date(state.month.getFullYear(), state.month.getMonth() + 1, 1);
  await loadEvents();
});

elements.themeButton.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme || "system";
  const next = current === "system" ? "dark" : current === "dark" ? "light" : "system";
  if (next === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = next;
  localStorage.setItem("goreecloud-calendar-theme", next);
  elements.themeButton.title = `Appearance: ${next}`;
});

function toast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => elements.toast.classList.add("hidden"), 3200);
}

const savedTheme = localStorage.getItem("goreecloud-calendar-theme");
if (savedTheme && savedTheme !== "system") document.documentElement.dataset.theme = savedTheme;
restoreSession();
