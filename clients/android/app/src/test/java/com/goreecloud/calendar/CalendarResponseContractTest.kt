package com.goreecloud.calendar

import java.time.OffsetDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CalendarResponseContractTest {
    @Test
    fun acceptsMinimizedEventViewEnvelope() {
        val envelope = CalendarEventsEnvelope(
            schema = CalendarResponseContract.EVENTS_SCHEMA,
            version = 1,
            view = "week",
            timezone = "America/Chicago",
            range = CalendarRangeWire(
                "2026-09-13T00:00:00-05:00",
                "2026-09-20T00:00:00-05:00",
            ),
            returned = 1,
            events = listOf(event()),
        )
        assertEquals(
            CalendarResponseDecision.Accepted(1),
            CalendarResponseContract.acceptEvents(
                envelope,
                CalendarViewMode.WEEK,
                "America/Chicago",
            ),
        )
    }

    @Test
    fun rejectsEventSchemaViewTimezoneAndCountDrift() {
        val base = eventsEnvelope()
        assertRejected(CalendarResponseContract.acceptEvents(base.copy(schema = "wrong"), CalendarViewMode.WEEK, "UTC"))
        assertRejected(CalendarResponseContract.acceptEvents(base.copy(view = "day"), CalendarViewMode.WEEK, "UTC"))
        assertRejected(CalendarResponseContract.acceptEvents(base.copy(timezone = "Europe/Paris"), CalendarViewMode.WEEK, "UTC"))
        assertRejected(CalendarResponseContract.acceptEvents(base.copy(returned = 2), CalendarViewMode.WEEK, "UTC"))
    }

    @Test
    fun rejectsInvalidEventRangesDuplicateUidsAndOutOfWindowEvents() {
        val duplicate = eventsEnvelope(events = listOf(event(), event()), returned = 2)
        val backwards = eventsEnvelope(
            events = listOf(event(startsAt = "2026-09-15T11:00:00+00:00", endsAt = "2026-09-15T10:00:00+00:00")),
        )
        val outside = eventsEnvelope(
            events = listOf(event(startsAt = "2026-10-01T10:00:00+00:00", endsAt = "2026-10-01T11:00:00+00:00")),
        )
        assertRejected(CalendarResponseContract.acceptEvents(duplicate, CalendarViewMode.WEEK, "UTC"))
        assertRejected(CalendarResponseContract.acceptEvents(backwards, CalendarViewMode.WEEK, "UTC"))
        assertRejected(CalendarResponseContract.acceptEvents(outside, CalendarViewMode.WEEK, "UTC"))
    }

    @Test
    fun acceptsStrictlyOrderedBusyProjectionMatchingRequest() {
        val start = OffsetDateTime.parse("2026-09-14T09:00:00-05:00")
        val end = OffsetDateTime.parse("2026-09-14T17:00:00-05:00")
        val envelope = CalendarBusyEnvelope(
            schema = CalendarResponseContract.BUSY_SCHEMA,
            version = 1,
            range = CalendarRangeWire(start.toString(), end.toString()),
            returned = 2,
            busy = listOf(
                BusyIntervalWire("2026-09-14T10:00:00-05:00", "2026-09-14T11:00:00-05:00"),
                BusyIntervalWire("2026-09-14T13:00:00-05:00", "2026-09-14T14:30:00-05:00"),
            ),
        )
        assertEquals(
            CalendarResponseDecision.Accepted(2),
            CalendarResponseContract.acceptBusy(envelope, start, end),
        )
    }

    @Test
    fun rejectsBusyRangeDriftOverlapAndEventDetailLeakage() {
        val start = OffsetDateTime.parse("2026-09-14T09:00:00-05:00")
        val end = OffsetDateTime.parse("2026-09-14T17:00:00-05:00")
        val base = busyEnvelope(start, end)
        val drift = base.copy(
            range = CalendarRangeWire("2026-09-14T08:00:00-05:00", end.toString()),
        )
        val overlap = base.copy(
            returned = 2,
            busy = listOf(
                BusyIntervalWire("2026-09-14T10:00:00-05:00", "2026-09-14T12:00:00-05:00"),
                BusyIntervalWire("2026-09-14T11:00:00-05:00", "2026-09-14T13:00:00-05:00"),
            ),
        )
        assertRejected(CalendarResponseContract.acceptBusy(drift, start, end))
        assertRejected(CalendarResponseContract.acceptBusy(overlap, start, end))
        assertTrue(
            CalendarResponseContract.unexpectedFields(
                setOf("starts_at", "ends_at", "title"),
                CalendarResponseContract.BUSY_INTERVAL_FIELDS,
            ).contains("title"),
        )
        assertTrue(
            CalendarResponseContract.unexpectedFields(
                setOf("starts_at", "ends_at", "uid"),
                CalendarResponseContract.BUSY_INTERVAL_FIELDS,
            ).contains("uid"),
        )
    }

    @Test
    fun exactFieldAllowlistsRejectCredentialAndBackendFields() {
        assertTrue(
            CalendarResponseContract.unexpectedFields(
                setOf("schema", "version", "events", "credential"),
                CalendarResponseContract.EVENTS_TOP_LEVEL_FIELDS,
            ).contains("credential"),
        )
        assertTrue(
            CalendarResponseContract.unexpectedFields(
                setOf("uid", "title", "calendar_href"),
                CalendarResponseContract.EVENT_FIELDS,
            ).contains("calendar_href"),
        )
    }

    private fun eventsEnvelope(
        returned: Int = 1,
        events: List<CalendarEventWire> = listOf(event()),
    ) = CalendarEventsEnvelope(
        schema = CalendarResponseContract.EVENTS_SCHEMA,
        version = 1,
        view = "week",
        timezone = "UTC",
        range = CalendarRangeWire("2026-09-14T00:00:00+00:00", "2026-09-21T00:00:00+00:00"),
        returned = returned,
        events = events,
    )

    private fun busyEnvelope(start: OffsetDateTime, end: OffsetDateTime) = CalendarBusyEnvelope(
        schema = CalendarResponseContract.BUSY_SCHEMA,
        version = 1,
        range = CalendarRangeWire(start.toString(), end.toString()),
        returned = 1,
        busy = listOf(BusyIntervalWire("2026-09-14T10:00:00-05:00", "2026-09-14T11:00:00-05:00")),
    )

    private fun event(
        uid: String = "event-1",
        startsAt: String = "2026-09-15T10:00:00+00:00",
        endsAt: String = "2026-09-15T11:00:00+00:00",
    ) = CalendarEventWire(
        uid = uid,
        title = "Review Calendar contract",
        startsAt = startsAt,
        endsAt = endsAt,
        description = "Development fixture",
        location = "",
        allDay = false,
        etag = "etag-1",
    )

    private fun assertRejected(decision: CalendarResponseDecision) {
        assertTrue(decision is CalendarResponseDecision.Rejected)
    }
}
