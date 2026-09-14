package com.goreecloud.calendar

import java.time.OffsetDateTime
import java.time.format.DateTimeParseException

data class CalendarRangeWire(val startsAt: String, val endsAt: String)

data class CalendarEventWire(
    val uid: String,
    val title: String,
    val startsAt: String,
    val endsAt: String,
    val description: String,
    val location: String,
    val allDay: Boolean,
    val etag: String?,
)

data class CalendarEventsEnvelope(
    val schema: String,
    val version: Int,
    val view: String,
    val timezone: String,
    val range: CalendarRangeWire,
    val returned: Int,
    val events: List<CalendarEventWire>,
)

data class BusyIntervalWire(val startsAt: String, val endsAt: String)

data class CalendarBusyEnvelope(
    val schema: String,
    val version: Int,
    val range: CalendarRangeWire,
    val returned: Int,
    val busy: List<BusyIntervalWire>,
)

sealed interface CalendarResponseDecision {
    data class Accepted(val itemCount: Int) : CalendarResponseDecision
    data class Rejected(val reason: String) : CalendarResponseDecision
}

/**
 * Transport-neutral acceptance policy for the current Calendar read API.
 *
 * This policy performs no HTTP, authentication, JSON parsing, persistence, provider access, or
 * synchronization. A future exact-field decoder must reject unknown fields using the allowlists
 * below before handing typed values to this contract. Radicale/CalDAV remains authoritative.
 */
object CalendarResponseContract {
    const val EVENTS_SCHEMA = "goreecloud.calendar.events.v1"
    const val BUSY_SCHEMA = "goreecloud.calendar.busy.v1"
    const val VERSION = 1

    val EVENTS_TOP_LEVEL_FIELDS = setOf(
        "schema", "version", "view", "timezone", "range", "returned", "events",
    )
    val EVENT_FIELDS = setOf(
        "uid", "title", "starts_at", "ends_at", "description", "location", "all_day", "etag",
    )
    val RANGE_FIELDS = setOf("starts_at", "ends_at")
    val BUSY_TOP_LEVEL_FIELDS = setOf("schema", "version", "range", "returned", "busy")
    val BUSY_INTERVAL_FIELDS = RANGE_FIELDS

    private const val MAX_EVENTS = 500
    private const val MAX_TEXT = 10_000
    private const val MAX_IDENTITY_TEXT = 4096
    private const val MAX_TIMEZONE = 128

    fun unexpectedFields(actual: Set<String>, allowed: Set<String>): Set<String> = actual - allowed

    fun acceptEvents(
        envelope: CalendarEventsEnvelope,
        expectedView: CalendarViewMode,
        expectedTimezone: String,
    ): CalendarResponseDecision {
        if (envelope.schema != EVENTS_SCHEMA) return reject("events schema mismatch")
        if (envelope.version != VERSION) return reject("events version mismatch")
        if (envelope.view != expectedView.wireValue) return reject("view mismatch")
        if (!validCanonicalText(expectedTimezone, MAX_TIMEZONE, allowEmpty = false)) {
            return reject("expected timezone is invalid")
        }
        if (envelope.timezone != expectedTimezone) return reject("timezone mismatch")
        val range = parsePositiveRange(envelope.range) ?: return reject("event range is invalid")
        if (envelope.returned < 0 || envelope.returned != envelope.events.size) {
            return reject("returned does not match events size")
        }
        if (envelope.events.size > MAX_EVENTS) return reject("too many events")
        if (envelope.events.map { it.uid }.toSet().size != envelope.events.size) {
            return reject("duplicate event uid")
        }
        envelope.events.forEachIndexed { index, event ->
            val eventRange = validateEvent(event) ?: return reject("event[$index]: invalid event")
            if (!(eventRange.first < range.second && range.first < eventRange.second)) {
                return reject("event[$index]: event is outside response range")
            }
        }
        return CalendarResponseDecision.Accepted(envelope.events.size)
    }

    fun acceptBusy(
        envelope: CalendarBusyEnvelope,
        expectedStartsAt: OffsetDateTime,
        expectedEndsAt: OffsetDateTime,
    ): CalendarResponseDecision {
        if (!expectedEndsAt.isAfter(expectedStartsAt)) return reject("expected busy range is invalid")
        if (envelope.schema != BUSY_SCHEMA) return reject("busy schema mismatch")
        if (envelope.version != VERSION) return reject("busy version mismatch")
        val range = parsePositiveRange(envelope.range) ?: return reject("busy range is invalid")
        if (range.first != expectedStartsAt || range.second != expectedEndsAt) {
            return reject("busy range does not match request")
        }
        if (envelope.returned < 0 || envelope.returned != envelope.busy.size) {
            return reject("returned does not match busy size")
        }
        if (envelope.busy.size > MAX_EVENTS) return reject("too many busy intervals")

        var previousEnd: OffsetDateTime? = null
        envelope.busy.forEachIndexed { index, interval ->
            val parsed = parsePositiveRange(CalendarRangeWire(interval.startsAt, interval.endsAt))
                ?: return reject("busy[$index]: interval is invalid")
            if (parsed.first < expectedStartsAt || parsed.second > expectedEndsAt) {
                return reject("busy[$index]: interval exceeds requested range")
            }
            previousEnd?.let { priorEnd ->
                if (!parsed.first.isAfter(priorEnd)) {
                    return reject("busy[$index]: intervals are overlapping or not strictly ordered")
                }
            }
            previousEnd = parsed.second
        }
        return CalendarResponseDecision.Accepted(envelope.busy.size)
    }

    private fun validateEvent(event: CalendarEventWire): Pair<OffsetDateTime, OffsetDateTime>? {
        if (!validCanonicalText(event.uid, MAX_IDENTITY_TEXT, allowEmpty = false)) return null
        if (!validCanonicalText(event.title, MAX_TEXT, allowEmpty = false)) return null
        if (!validContentText(event.description, MAX_TEXT)) return null
        if (!validContentText(event.location, MAX_TEXT)) return null
        if (event.etag != null && !validCanonicalText(event.etag, MAX_IDENTITY_TEXT, allowEmpty = false)) {
            return null
        }
        return parsePositiveRange(CalendarRangeWire(event.startsAt, event.endsAt))
    }

    private fun parsePositiveRange(range: CalendarRangeWire): Pair<OffsetDateTime, OffsetDateTime>? {
        val start = parseOffset(range.startsAt) ?: return null
        val end = parseOffset(range.endsAt) ?: return null
        if (!end.isAfter(start)) return null
        return start to end
    }

    private fun parseOffset(value: String): OffsetDateTime? = try {
        OffsetDateTime.parse(value)
    } catch (_: DateTimeParseException) {
        null
    }

    private fun validCanonicalText(value: String, maxLength: Int, allowEmpty: Boolean): Boolean {
        if (value.length > maxLength) return false
        if (!allowEmpty && value.isEmpty()) return false
        if (value != value.trim()) return false
        return value.none(Char::isISOControl)
    }

    private fun validContentText(value: String, maxLength: Int): Boolean {
        if (value.length > maxLength) return false
        return value.none { it.isISOControl() && it != '\n' && it != '\r' && it != '\t' }
    }

    private fun reject(reason: String): CalendarResponseDecision.Rejected =
        CalendarResponseDecision.Rejected(reason)
}
