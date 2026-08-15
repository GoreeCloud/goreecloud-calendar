# GoreeCloud Calendar — Glaze UI Web Implementation

GoreeCloud Calendar uses **Glaze UI** as its required web design and interaction language.

This document records the application-level implementation boundary so visual work remains intentional, reviewable, and reusable rather than becoming a collection of isolated CSS effects.

## Design-layer separation

The web frontend uses two CSS layers:

- `frontend/glaze.css` — shared Glaze UI foundations: design tokens, surfaces, controls, fields, focus behavior, status presentation, theme architecture, motion and accessibility fallbacks.
- `frontend/styles.css` — Calendar-specific layout and product composition: application shell, month grid, schedule view, calendar navigation, context rail, event presentation, dialogs, and responsive adaptations.

This separation is deliberate. Calendar may evolve its product-specific layout without redefining the shared Glaze UI primitives every time.

## Glaze UI implementation mapping

### Layered surfaces and selective translucency

Primary navigation, the calendar workspace, context rail, authentication surface, dialogs, mobile action bar, and transient feedback use layered Glaze surfaces. Translucency is selective rather than universal. Content-heavy areas retain stronger opaque surfaces when that improves readability.

### Rounded geometry and softened depth

Controls, fields, navigation selections, cards, dialogs, event surfaces, calendar accents, and containers use shared radius and shadow tokens. Elevation is used to establish hierarchy without relying on heavy outlines.

### Purposeful gradients and GoreeCloud identity

The interface uses restrained GoreeCloud accent gradients and ambient color fields to establish product identity and dimensional continuity. Decorative effects remain behind content and are suppressed when the operating system requests reduced transparency.

### Typography and spacing

Calendar uses the local operating-system UI font stack only. No external web font is loaded. Shared spacing, radius, type, surface, and motion tokens live in `glaze.css`; Calendar-specific compositions consume those foundations.

### Navigation and search

Desktop and larger tablet layouts provide a persistent calendar-navigation panel with Month and Schedule views, calendar selection, creation, refresh controls, and keyboard hints. Search is a first-class top-level control and filters the currently loaded view without sending search text to a third party.

### Theme architecture

Calendar supports:

- system appearance;
- explicit light appearance;
- explicit dark appearance.

Only the appearance preference is stored in browser `localStorage`. Calendar data, DAV credentials, event content, and authentication material are not stored there.

### Accessibility and interaction

The Glaze web layer includes:

- visible keyboard focus;
- semantic buttons and form labels;
- explicit button types;
- keyboard shortcuts for common calendar actions;
- touch-appropriate mobile controls;
- screen-reader labels for icon-only controls;
- live regions for connection state, errors, loading feedback, and toast feedback;
- `prefers-reduced-motion` support;
- `prefers-reduced-transparency` support;
- custom application confirmation UI instead of browser-native destructive confirmation.

Visual treatments must not override readable contrast, clear state, or predictable interaction.

## Calendar product views

### Month

Month is the primary spatial calendar view. It preserves the familiar seven-column month model while using GoreeCloud event colors, keyboard-focusable event controls, current-day emphasis, and a controlled transition to Schedule when a day contains more events than can be shown comfortably.

### Schedule

Schedule provides a vertically scannable alternative to the month grid. Events are grouped by date with calendar-color accents, time information, calendar context, location context, and the same event detail/edit boundary as Month.

### Today and Coming Up

Wide desktop layouts include a contextual rail for today and the next visible events. This is a convenience view over the same currently loaded CalDAV data; it does not create a second data source or cache.

## Responsive behavior

The web application changes interaction structure rather than merely shrinking the desktop shell:

- the desktop calendar panel becomes an overlay panel on mobile;
- a dedicated mobile quick-action bar provides Today, Calendars, and New Event actions;
- the wide desktop context rail is removed when it would crowd the primary calendar task;
- dialogs collapse multi-column form rows to a single column;
- event density and secondary text are reduced at narrower widths;
- search remains available from the mobile application header.

## Privacy and dependency boundary

The frontend remains self-contained:

- no remote scripts;
- no remote stylesheets;
- no remote fonts;
- no analytics;
- no trackers;
- no advertising SDKs;
- no CDN dependency.

The browser communicates only with the same-origin GoreeCloud Calendar backend. The backend remains responsible for authenticated CalDAV access to `dav.goreecloud.com`.

## Validation

`scripts/validate_frontend.py` performs repository-level structural validation for the Glaze UI web implementation. CI also validates JavaScript syntax before Docker and backend checks complete.

Structural validation does not replace visual acceptance. Before a Stable release, Calendar still requires representative browser and viewport review in light, dark, and system appearance modes, keyboard-only interaction review, mobile/touch review, and accessibility acceptance.
