const state = {
  session: null,
  calendars: [],
  selected: new Set(),
  selectionInitialized: false,
  events: [],
  month: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  editing: null,
  view: "month",
  search: "",
  loading: false,
  toastTimer: null,
  confirmAction: null,
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
  eventSearch: $("eventSearch"),
  syncState: $("syncState"),
  themeButton: $("themeButton"),
  calendarPanel: $("calendarPanel"),
  calendarPanelToggle: $("calendarPanelToggle"),
  calendarPanelClose: $("calendarPanelClose"),
  mobileCalendarsButton: $("mobileCalendarsButton"),
  calendarList: $("calendarList"),
  refreshButton: $("refreshButton"),
  selectAllButton: $("selectAllButton"),
  selectNoneButton: $("selectNoneButton"),
  newEventButton: $("newEventButton"),
  mobileNewButton: $("mobileNewButton"),
  todayButton: $("todayButton"),
  mobileTodayButton: $("mobileTodayButton"),
  prevButton: $("prevButton"),
  nextButton: $("nextButton"),
  monthTitle: $("monthTitle"),
  viewEyebrow: $("viewEyebrow"),
  monthNavButton: $("monthNavButton"),
  scheduleNavButton: $("scheduleNavButton"),
  monthViewButton: $("monthViewButton"),
  scheduleViewButton: $("scheduleViewButton"),
  monthView: $("monthView"),
  scheduleView: $("scheduleView"),
  calendarGrid: $("calendarGrid"),
  scheduleList: $("scheduleList"),
  emptyState: $("emptyState"),
  emptyStateCopy: $("emptyStateCopy"),
  loadingState: $("loadingState"),
  todayHeading: $("todayHeading"),
  todayDate: $("todayDate"),
  todayEvents: $("todayEvents"),
  upcomingEvents: $("upcomingEvents"),
  eventDialog: $("eventDialog"),
  eventForm: $("eventForm"),
  dialogTitle: $("dialogTitle"),
  readOnlyBadge: $("readOnlyBadge"),
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
  confirmDialog: $("confirmDialog"),
  confirmTitle: $("confirmTitle"),
  confirmCopy: $("confirmCopy"),
  confirmCancelButton: $("confirmCancelButton"),
  confirmActionButton: $("confirmActionButton"),
  toast: $("toast"),
};

const fallbackColors = ["#4f68dc", "#7b5dcc", "#238b78", "#c16c3b", "#ad4e6c", "#5b7e33"];
const themeOrder = ["system", "light", "dark"];

async function api(path, options = {}) {
  const { allowUnauthorized = false, ...fetchOptions } = options;
  const headers = { ...(fetchOptions.headers || {}) };
  if (fetchOptions.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const method = (fetchOptions.method || "GET").toUpperCase();
  if (state.session?.csrf_token && !["GET", "HEAD"].includes(method)) {
    headers["X-CSRF-Token"] = state.session.csrf_token;
  }

  const response = await fetch(path, {
    credentials: "same-origin",
    ...fetchOptions,
    headers,
  });

  if (response.status === 401 && !allowUnauthorized) {
    showLogin();
    throw new Error("Your session has expired. Sign in again.");
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (payload.detail) detail = JSON.stringify(payload.detail);
    } catch (_) {}
    const retryAfter = response.headers.get("Retry-After");
    if (response.status === 429 && retryAfter) detail = `${detail} Try again in about ${retryAfter} seconds.`;
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}

function showLogin() {
  state.session = null;
  state.calendars = [];
  state.events = [];
  state.selected.clear();
  state.selectionInitialized = false;
  state.editing = null;
  setLoading(false);
  closeCalendarPanel();
  elements.appView.classList.add("hidden");
  elements.loginView.classList.remove("hidden");
  elements.password.value = "";
  queueMicrotask(() => elements.username.focus());
}

function showApp() {
  elements.loginView.classList.add("hidden");
  elements.appView.classList.remove("hidden");
  elements.userLabel.textContent = state.session.username;
  updateWriteControls();
}

function updateWriteControls() {
  const writable = Boolean(state.session?.write_enabled && state.calendars.length > 0);
  [elements.newEventButton, elements.mobileNewButton].forEach((button) => {
    button.disabled = !writable;
    button.title = writable ? "Create an event" : "CalDAV writes are disabled or no calendars are available";
  });
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

function setSyncState(label, mode = "ok") {
  const labelNode = elements.syncState.querySelector("span:last-child");
  if (labelNode) labelNode.textContent = label;
  elements.syncState.dataset.state = mode;
}

function setLoading(loading) {
  state.loading = loading;
  elements.loadingState.classList.toggle("hidden", !loading);
  elements.calendarGrid.setAttribute("aria-busy", String(loading));
  elements.scheduleList.setAttribute("aria-busy", String(loading));
}

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.loginError.textContent = "";
  const button = elements.loginForm.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    state.session = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: elements.username.value.trim(), password: elements.password.value }),
      allowUnauthorized: true,
    });
    elements.password.value = "";
    showApp();
    await refreshAll();
  } catch (error) {
    elements.loginError.textContent = error.status === 401 ? "The username or password was not accepted." : error.message;
  } finally {
    button.disabled = false;
  }
});

elements.logoutButton.addEventListener("click", async () => {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (_) {}
  showLogin();
});

function calendarColor(calendar, index) {
  const candidate = calendar?.color || "";
  if (/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(candidate)) return candidate.slice(0, 7);
  return fallbackColors[Math.max(index, 0) % fallbackColors.length];
}

async function refreshAll() {
  setSyncState("Syncing", "syncing");
  setLoading(true);
  try {
    state.calendars = await api("/api/calendars");
    if (!state.selectionInitialized) {
      state.calendars.forEach((calendar) => state.selected.add(calendar.href));
      state.selectionInitialized = true;
    } else {
      const valid = new Set(state.calendars.map((calendar) => calendar.href));
      state.selected = new Set([...state.selected].filter((href) => valid.has(href)));
    }
    populateCalendarSelect();
    updateWriteControls();
    await loadEvents({ manageLoading: false });
    renderCalendarList();
    setSyncState("Connected", "ok");
  } catch (error) {
    setSyncState("Connection issue", "error");
    renderCurrentView();
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

function calendarVisibleCount(calendarHref) {
  return filteredEvents().filter((event) => event.calendar_href === calendarHref).length;
}

function renderCalendarList() {
  elements.calendarList.replaceChildren();
  if (state.calendars.length === 0) {
    const empty = document.createElement("p");
    empty.className = "glaze-muted";
    empty.style.fontSize = ".72rem";
    empty.textContent = "No calendars are available for this account.";
    elements.calendarList.append(empty);
    return;
  }

  state.calendars.forEach((calendar, index) => {
    const label = document.createElement("label");
    label.className = "calendar-option";
    label.style.setProperty("--calendar-color", calendarColor(calendar, index));

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(calendar.href);
    checkbox.setAttribute("aria-label", `Show ${calendar.display_name}`);
    checkbox.addEventListener("change", async () => {
      if (checkbox.checked) state.selected.add(calendar.href);
      else state.selected.delete(calendar.href);
      await loadEvents();
    });

    const dot = document.createElement("span");
    dot.className = "calendar-dot";
    dot.setAttribute("aria-hidden", "true");

    const name = document.createElement("span");
    name.className = "calendar-name";
    name.textContent = calendar.display_name;
    if (calendar.description) name.title = calendar.description;

    const count = document.createElement("span");
    count.className = "calendar-count";
    count.textContent = String(calendarVisibleCount(calendar.href));
    count.title = "Events in loaded view";

    label.append(checkbox, dot, name, count);
    elements.calendarList.append(label);
  });
}

function populateCalendarSelect() {
  const previous = elements.eventCalendar.value;
  elements.eventCalendar.replaceChildren();
  state.calendars.forEach((calendar) => {
    const option = document.createElement("option");
    option.value = calendar.href;
    option.textContent = calendar.display_name;
    elements.eventCalendar.append(option);
  });
  if (state.calendars.some((calendar) => calendar.href === previous)) elements.eventCalendar.value = previous;
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

async function loadEvents({ manageLoading = true } = {}) {
  if (manageLoading) setLoading(true);
  state.events = [];
  const { start, end } = monthGridRange();
  const selected = state.calendars.filter((calendar) => state.selected.has(calendar.href));
  try {
    if (selected.length) {
      const groups = await Promise.all(selected.map((calendar) =>
        api(`/api/events?calendar_href=${encodeURIComponent(calendar.href)}&start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}`)
      ));
      state.events = groups.flat();
    }
    renderCurrentView();
    renderCalendarList();
  } catch (error) {
    renderCurrentView();
    toast(error.message);
  } finally {
    if (manageLoading) setLoading(false);
  }
}

function filteredEvents() {
  const query = state.search.trim().toLocaleLowerCase();
  if (!query) return state.events;
  return state.events.filter((event) => {
    const calendar = state.calendars.find((item) => item.href === event.calendar_href);
    return [event.summary, event.description, event.location, calendar?.display_name]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase().includes(query));
  });
}

function renderCurrentView(focusDate = null) {
  renderMonth();
  renderSchedule(focusDate);
  renderRail();
  updateEmptyState();
}

function renderMonth() {
  elements.monthTitle.textContent = state.month.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  elements.viewEyebrow.textContent = state.view === "month" ? "Month view" : "Schedule view";
  const { start } = monthGridRange();
  const todayKey = dateKey(new Date());
  const visible = filteredEvents();
  elements.calendarGrid.replaceChildren();

  for (let i = 0; i < 42; i += 1) {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    const key = dateKey(day);
    const cell = document.createElement("div");
    cell.className = "day-cell";
    cell.setAttribute("role", "gridcell");
    cell.setAttribute("aria-label", day.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }));
    cell.dataset.date = key;
    if (day.getMonth() !== state.month.getMonth()) cell.classList.add("outside-month");
    if (key === todayKey) cell.classList.add("today");

    let dayNumber;
    if (state.session?.write_enabled && state.calendars.length) {
      dayNumber = document.createElement("button");
      dayNumber.type = "button";
      dayNumber.className = "day-number can-create";
      dayNumber.setAttribute("aria-label", `${day.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })}; create event`);
      dayNumber.addEventListener("click", () => openNewEvent(day));
    } else {
      dayNumber = document.createElement("span");
      dayNumber.className = "day-number";
    }
    dayNumber.textContent = day.getDate();
    cell.append(dayNumber);

    const stack = document.createElement("div");
    stack.className = "event-stack";
    const dayEvents = visible
      .filter((item) => eventTouchesDay(item, day))
      .sort(compareEvents);

    dayEvents.slice(0, 4).forEach((item) => stack.append(createEventChip(item)));
    if (dayEvents.length > 4) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "more-events-button";
      more.textContent = `+${dayEvents.length - 4} more`;
      more.setAttribute("aria-label", `Show ${dayEvents.length - 4} more events for ${day.toLocaleDateString()}`);
      more.addEventListener("click", () => switchView("schedule", day));
      stack.append(more);
    }
    cell.append(stack);
    elements.calendarGrid.append(cell);
  }
}

function createEventChip(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-chip";
  const index = state.calendars.findIndex((calendar) => calendar.href === item.calendar_href);
  button.style.setProperty("--event-color", calendarColor(state.calendars[index], index));
  button.title = eventTooltip(item);
  button.setAttribute("aria-label", eventTooltip(item));

  if (!item.all_day) {
    const time = document.createElement("span");
    time.className = "event-chip-time";
    time.textContent = formatTime(item.start);
    button.append(time);
  }
  if (item.recurring) {
    const recurring = document.createElement("span");
    recurring.className = "event-chip-recurring";
    recurring.textContent = "↻";
    recurring.setAttribute("aria-hidden", "true");
    button.append(recurring);
  }
  const title = document.createElement("span");
  title.className = "event-chip-title";
  title.textContent = item.summary;
  button.append(title);
  button.addEventListener("click", () => openEventDialog(item));
  return button;
}

function renderSchedule(focusDate = null) {
  elements.scheduleList.replaceChildren();
  const visible = [...filteredEvents()].sort(compareEvents);
  const groups = new Map();

  visible.forEach((event) => {
    const start = eventStartDate(event);
    const key = dateKey(start);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(event);
  });

  [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).forEach(([key, events]) => {
    const day = parseDateKey(key);
    const section = document.createElement("section");
    section.className = "schedule-day";
    section.dataset.date = key;

    const heading = document.createElement("div");
    heading.className = "schedule-day-heading";
    const dateBlock = document.createElement("div");
    dateBlock.className = "schedule-date-block";
    const number = document.createElement("strong");
    number.textContent = day.getDate();
    const weekday = document.createElement("span");
    weekday.textContent = day.toLocaleDateString(undefined, { weekday: "short" });
    dateBlock.append(number, weekday);
    const title = document.createElement("div");
    title.className = "schedule-day-title";
    const titleStrong = document.createElement("strong");
    titleStrong.textContent = day.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
    const titleMeta = document.createElement("span");
    titleMeta.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
    title.append(titleStrong, titleMeta);
    heading.append(dateBlock, title);

    const eventList = document.createElement("div");
    eventList.className = "schedule-events";
    events.forEach((event) => eventList.append(createScheduleEvent(event)));
    section.append(heading, eventList);
    elements.scheduleList.append(section);
  });

  if (focusDate && state.view === "schedule") {
    requestAnimationFrame(() => {
      const target = elements.scheduleList.querySelector(`[data-date="${dateKey(focusDate)}"]`);
      target?.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
  }
}

function createScheduleEvent(item) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "schedule-event";
  const index = state.calendars.findIndex((calendar) => calendar.href === item.calendar_href);
  button.style.setProperty("--event-color", calendarColor(state.calendars[index], index));
  button.setAttribute("aria-label", eventTooltip(item));

  const accent = document.createElement("span");
  accent.className = "schedule-event-accent";
  accent.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  copy.className = "schedule-event-copy";
  const title = document.createElement("strong");
  title.textContent = `${item.recurring ? "↻ " : ""}${item.summary}`;
  const meta = document.createElement("span");
  const calendar = state.calendars[index];
  meta.textContent = [calendar?.display_name, item.location].filter(Boolean).join(" · ") || "GoreeCloud Calendar";
  copy.append(title, meta);
  const time = document.createElement("span");
  time.className = "schedule-event-time";
  time.textContent = item.all_day ? "All day" : formatTimeRange(item);
  button.append(accent, copy, time);
  button.addEventListener("click", () => openEventDialog(item));
  return button;
}

function renderRail() {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  elements.todayHeading.textContent = today.toLocaleDateString(undefined, { weekday: "long" });
  elements.todayDate.textContent = String(today.getDate());

  const visible = [...filteredEvents()].sort(compareEvents);
  const todayEvents = visible.filter((event) => eventTouchesDay(event, today));
  const upcoming = visible.filter((event) => eventEndDate(event) >= now && !todayEvents.includes(event)).slice(0, 5);
  renderRailEvents(elements.todayEvents, todayEvents.slice(0, 5), "Nothing scheduled in the loaded view today.");
  renderRailEvents(elements.upcomingEvents, upcoming, "No upcoming events in this loaded view.");
}

function renderRailEvents(container, events, emptyCopy) {
  container.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("p");
    empty.className = "rail-empty";
    empty.textContent = emptyCopy;
    container.append(empty);
    return;
  }
  events.forEach((event) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "rail-event";
    const index = state.calendars.findIndex((calendar) => calendar.href === event.calendar_href);
    button.style.setProperty("--event-color", calendarColor(state.calendars[index], index));
    const line = document.createElement("span");
    line.className = "rail-event-line";
    line.setAttribute("aria-hidden", "true");
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = `${event.recurring ? "↻ " : ""}${event.summary}`;
    const meta = document.createElement("span");
    meta.textContent = event.all_day ? "All day" : formatTimeRange(event);
    copy.append(title, meta);
    button.append(line, copy);
    button.addEventListener("click", () => openEventDialog(event));
    container.append(button);
  });
}

function updateEmptyState() {
  const count = filteredEvents().length;
  const hidden = state.loading || count > 0;
  elements.emptyState.classList.toggle("hidden", hidden);
  if (state.search.trim()) {
    elements.emptyStateCopy.textContent = `No events match “${state.search.trim()}” in the loaded view.`;
  } else if (state.selected.size === 0) {
    elements.emptyStateCopy.textContent = "Select at least one calendar to show events.";
  } else {
    elements.emptyStateCopy.textContent = state.session?.write_enabled
      ? "This view is clear. Create an event whenever you are ready."
      : "This view is clear. CalDAV writes are currently disabled by the safety gate.";
  }
}

function switchView(view, focusDate = null) {
  if (!["month", "schedule"].includes(view)) return;
  state.view = view;
  const monthActive = view === "month";
  elements.monthView.classList.toggle("hidden", !monthActive);
  elements.scheduleView.classList.toggle("hidden", monthActive);
  [[elements.monthNavButton, monthActive], [elements.monthViewButton, monthActive], [elements.scheduleNavButton, !monthActive], [elements.scheduleViewButton, !monthActive]].forEach(([button, active]) => {
    button.classList.toggle("is-active", active);
    if (button.classList.contains("view-switch")) button.setAttribute("aria-pressed", String(active));
    if (button.classList.contains("nav-item")) {
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    }
  });
  renderCurrentView(focusDate);
  closeCalendarPanel();
}

function dateKey(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseDateKey(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function eventStartDate(event) {
  return event.all_day ? parseDateKey(event.start) : new Date(event.start);
}

function eventEndDate(event) {
  if (event.all_day) {
    return event.end ? parseDateKey(event.end) : new Date(eventStartDate(event).getTime() + 86400000);
  }
  if (event.end) return new Date(event.end);
  return new Date(new Date(event.start).getTime() + 1);
}

function compareEvents(a, b) {
  return eventStartDate(a) - eventStartDate(b) || a.summary.localeCompare(b.summary);
}

function eventTouchesDay(event, day) {
  const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate());
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayEnd.getDate() + 1);
  const start = eventStartDate(event);
  const end = eventEndDate(event);
  return start < dayEnd && end > dayStart;
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function formatTimeRange(event) {
  const start = formatTime(event.start);
  return event.end ? `${start}–${formatTime(event.end)}` : start;
}

function eventTooltip(event) {
  const when = event.all_day
    ? `${event.start}${event.end ? ` through ${event.end}` : ""}, all day`
    : new Date(event.start).toLocaleString();
  return [event.summary, when, event.location].filter(Boolean).join(" — ");
}

function toLocalInput(iso) {
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function setEventFormReadOnly(readOnly) {
  [elements.eventCalendar, elements.eventSummary, elements.eventAllDay, elements.eventStart, elements.eventEnd, elements.eventLocation, elements.eventDescription]
    .forEach((control) => { control.disabled = readOnly; });
  elements.readOnlyBadge.classList.toggle("hidden", !readOnly);
}

function openNewEvent(day = new Date()) {
  if (!state.session?.write_enabled || !state.calendars.length) return;
  state.editing = null;
  setEventFormReadOnly(false);
  elements.dialogTitle.textContent = "New event";
  elements.eventHref.value = "";
  elements.eventEtag.value = "";
  elements.eventSummary.value = "";
  elements.eventLocation.value = "";
  elements.eventDescription.value = "";
  elements.eventAllDay.checked = false;
  elements.eventStart.type = "datetime-local";
  elements.eventEnd.type = "datetime-local";
  const start = new Date(day);
  start.setHours(9, 0, 0, 0);
  const end = new Date(start);
  end.setHours(10, 0, 0, 0);
  elements.eventStart.value = toLocalInput(start.toISOString());
  elements.eventEnd.value = toLocalInput(end.toISOString());
  elements.eventCalendar.value = [...state.selected][0] || state.calendars[0]?.href || "";
  elements.deleteEventButton.classList.add("hidden");
  elements.eventWarning.classList.add("hidden");
  elements.eventWarning.textContent = "";
  elements.eventError.textContent = "";
  elements.saveEventButton.disabled = false;
  elements.eventDialog.showModal();
  queueMicrotask(() => elements.eventSummary.focus());
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
  setDateInputMode(event.all_day, false);
  if (event.all_day) {
    elements.eventStart.value = event.start;
    elements.eventEnd.value = event.end || "";
  } else {
    elements.eventStart.value = toLocalInput(event.start);
    elements.eventEnd.value = event.end ? toLocalInput(event.end) : "";
  }

  const readOnly = !state.session?.write_enabled || event.recurring;
  setEventFormReadOnly(readOnly);
  elements.saveEventButton.disabled = readOnly;
  elements.deleteEventButton.classList.toggle("hidden", readOnly || !event.etag);
  elements.eventWarning.textContent = event.recurring
    ? "This occurrence belongs to a recurring series. Recurring edits and deletes stay read-only until recurrence write semantics are fully validated."
    : (!state.session?.write_enabled ? "CalDAV writes are disabled by the GoreeCloud Calendar safety gate." : "");
  elements.eventWarning.classList.toggle("hidden", !elements.eventWarning.textContent);
  elements.eventError.textContent = "";
  elements.eventDialog.showModal();
}

function setDateInputMode(allDay, preserve = true) {
  const startValue = elements.eventStart.value;
  const endValue = elements.eventEnd.value;
  elements.eventStart.type = allDay ? "date" : "datetime-local";
  elements.eventEnd.type = allDay ? "date" : "datetime-local";
  if (!preserve) return;

  if (allDay) {
    if (startValue) elements.eventStart.value = startValue.slice(0, 10);
    if (endValue) elements.eventEnd.value = endValue.slice(0, 10);
  } else {
    if (startValue && startValue.length === 10) elements.eventStart.value = `${startValue}T09:00`;
    if (endValue && endValue.length === 10) elements.eventEnd.value = `${endValue}T10:00`;
  }
}

elements.eventAllDay.addEventListener("change", () => setDateInputMode(elements.eventAllDay.checked));

function eventPayload() {
  const allDay = elements.eventAllDay.checked;
  const start = elements.eventStart.value;
  const end = elements.eventEnd.value;
  const payload = {
    calendar_href: elements.eventCalendar.value,
    summary: elements.eventSummary.value.trim(),
    description: elements.eventDescription.value,
    location: elements.eventLocation.value,
    start: allDay ? start : new Date(start).toISOString(),
    end: end ? (allDay ? end : new Date(end).toISOString()) : null,
    all_day: allDay,
  };
  if (state.editing?.etag) payload.etag = state.editing.etag;
  return payload;
}

elements.eventForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.session?.write_enabled || elements.saveEventButton.disabled) return;
  elements.eventError.textContent = "";
  elements.saveEventButton.disabled = true;
  try {
    const payload = eventPayload();
    if (!payload.summary) throw new Error("Event title is required.");
    if (!payload.start) throw new Error("Event start is required.");

    if (state.editing) {
      await api(`/api/events?event_href=${encodeURIComponent(state.editing.href)}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("Event updated.");
    } else {
      await api("/api/events", { method: "POST", body: JSON.stringify(payload) });
      state.selected.add(payload.calendar_href);
      toast("Event created.");
    }
    elements.eventDialog.close();
    await loadEvents();
  } catch (error) {
    elements.eventError.textContent = error.message;
    elements.saveEventButton.disabled = false;
  }
});

function askConfirmation({ title, copy, actionLabel, action }) {
  if (!elements.confirmDialog) return;
  state.confirmAction = action;
  elements.confirmTitle.textContent = title;
  elements.confirmCopy.textContent = copy;
  elements.confirmActionButton.textContent = actionLabel;
  elements.confirmDialog.showModal();
}

elements.deleteEventButton.addEventListener("click", () => {
  if (!state.editing || state.editing.recurring || !state.editing.etag) return;
  askConfirmation({
    title: "Delete this event?",
    copy: `“${state.editing.summary}” will be removed from its CalDAV calendar. This cannot be undone from Calendar.`,
    actionLabel: "Delete event",
    action: async () => {
      await api(`/api/events?event_href=${encodeURIComponent(state.editing.href)}&etag=${encodeURIComponent(state.editing.etag)}`, { method: "DELETE" });
      elements.eventDialog.close();
      toast("Event deleted.");
      await loadEvents();
    },
  });
});

if (elements.confirmCancelButton) elements.confirmCancelButton.addEventListener("click", () => {
  state.confirmAction = null;
  elements.confirmDialog.close();
});
if (elements.confirmActionButton) elements.confirmActionButton.addEventListener("click", async () => {
  const action = state.confirmAction;
  if (!action) return;
  elements.confirmActionButton.disabled = true;
  try {
    await action();
    state.confirmAction = null;
    elements.confirmDialog.close();
  } catch (error) {
    toast(error.message);
  } finally {
    elements.confirmActionButton.disabled = false;
  }
});

elements.closeDialogButton.addEventListener("click", () => elements.eventDialog.close());
elements.cancelEventButton.addEventListener("click", () => elements.eventDialog.close());

function goToday() {
  const today = new Date();
  state.month = new Date(today.getFullYear(), today.getMonth(), 1);
  loadEvents();
}

function changeMonth(delta) {
  state.month = new Date(state.month.getFullYear(), state.month.getMonth() + delta, 1);
  loadEvents();
}

elements.todayButton.addEventListener("click", goToday);
elements.mobileTodayButton.addEventListener("click", goToday);
elements.prevButton.addEventListener("click", () => changeMonth(-1));
elements.nextButton.addEventListener("click", () => changeMonth(1));
elements.refreshButton.addEventListener("click", refreshAll);
elements.newEventButton.addEventListener("click", () => openNewEvent());
elements.mobileNewButton.addEventListener("click", () => openNewEvent());

elements.selectAllButton.addEventListener("click", async () => {
  state.calendars.forEach((calendar) => state.selected.add(calendar.href));
  await loadEvents();
});
elements.selectNoneButton.addEventListener("click", async () => {
  state.selected.clear();
  await loadEvents();
});

[elements.monthNavButton, elements.monthViewButton].forEach((button) => button.addEventListener("click", () => switchView("month")));
[elements.scheduleNavButton, elements.scheduleViewButton].forEach((button) => button.addEventListener("click", () => switchView("schedule")));

elements.eventSearch.addEventListener("input", () => {
  state.search = elements.eventSearch.value;
  renderCurrentView();
  renderCalendarList();
});

function openCalendarPanel() {
  elements.calendarPanel.dataset.open = "true";
  elements.calendarPanelToggle.setAttribute("aria-expanded", "true");
  queueMicrotask(() => elements.calendarPanelClose.focus());
}
function closeCalendarPanel() {
  elements.calendarPanel.removeAttribute("data-open");
  elements.calendarPanelToggle.setAttribute("aria-expanded", "false");
}
elements.calendarPanelToggle.addEventListener("click", openCalendarPanel);
elements.mobileCalendarsButton.addEventListener("click", openCalendarPanel);
elements.calendarPanelClose.addEventListener("click", closeCalendarPanel);

function currentThemePreference() {
  try { return localStorage.getItem("goreecloud-calendar-theme") || "system"; } catch (_) { return "system"; }
}

function applyTheme(preference) {
  if (!themeOrder.includes(preference)) preference = "system";
  if (preference === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = preference;
  try { localStorage.setItem("goreecloud-calendar-theme", preference); } catch (_) {}
  elements.themeButton.setAttribute("aria-label", `Appearance: ${preference}. Activate to change.`);
  elements.themeButton.title = `Appearance: ${preference}`;
  updateThemeColor(preference);
}

function updateThemeColor(preference = currentThemePreference()) {
  const dark = preference === "dark" || (preference === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0f1621" : "#f4f7fb");
}

elements.themeButton.addEventListener("click", () => {
  const current = currentThemePreference();
  const next = themeOrder[(themeOrder.indexOf(current) + 1) % themeOrder.length];
  applyTheme(next);
  toast(`Appearance set to ${next}.`);
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
  if (currentThemePreference() === "system") updateThemeColor("system");
});

function isTypingTarget(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && elements.calendarPanel.dataset.open === "true") {
    closeCalendarPanel();
    elements.calendarPanelToggle.focus();
    return;
  }
  if (!state.session || elements.eventDialog.open || elements.confirmDialog?.open || isTypingTarget(event.target)) return;

  if (event.key === "/") {
    event.preventDefault();
    elements.eventSearch.focus();
    return;
  }
  if (event.key.toLowerCase() === "n" && state.session.write_enabled) {
    event.preventDefault();
    openNewEvent();
    return;
  }
  if (event.key.toLowerCase() === "t") {
    event.preventDefault();
    goToday();
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    changeMonth(-1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    changeMonth(1);
  }
});

function toast(message) {
  clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  state.toastTimer = setTimeout(() => elements.toast.classList.add("hidden"), 4200);
}

applyTheme(currentThemePreference());
restoreSession();
