package com.goreecloud.calendar

import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.time.LocalDate
import java.time.OffsetDateTime

enum class CalendarReadContractState {
    SOURCE_READY,
    IDENTITY_BLOCKED,
    TRANSPORT_BLOCKED,
}

data class CalendarReadContractSnapshot(
    val eventListing: CalendarReadContractState,
    val busyTime: CalendarReadContractState,
    val responseAcceptance: CalendarReadContractState,
    val nativeIdentityBindingContract: CalendarReadContractState,
    val nativeIdentitySession: CalendarReadContractState,
    val networkTransport: CalendarReadContractState,
)

enum class CalendarViewMode(val wireValue: String) {
    MONTH("month"),
    WEEK("week"),
    DAY("day"),
    AGENDA("agenda"),
}

/**
 * Pure Android-side model of the existing GoreeCloud Calendar read API.
 *
 * Calendar scope and user identity remain server-authorized. This contract only builds relative
 * request paths and cannot choose another host, user, credential, or CalDAV backend.
 */
object CalendarReadContract {
    const val EVENTS_PATH = "/api/v1/events"
    const val BUSY_TIME_PATH = "/api/v1/busy-time"

    private const val MAX_CALENDAR_HREF_LENGTH = 4096
    private const val MAX_TIMEZONE_LENGTH = 128

    fun eventsPath(
        calendarHref: String,
        anchor: LocalDate,
        view: CalendarViewMode = CalendarViewMode.MONTH,
        timezone: String = "UTC",
    ): String {
        val href = requireCalendarHref(calendarHref)
        val zone = requireTimezone(timezone)
        return buildString {
            append(EVENTS_PATH)
            append("?calendar=")
            append(encode(href))
            append("&anchor=")
            append(anchor)
            append("&view=")
            append(view.wireValue)
            append("&timezone=")
            append(encode(zone))
        }
    }

    fun busyTimePath(
        calendarHref: String,
        startsAt: OffsetDateTime,
        endsAt: OffsetDateTime,
    ): String {
        require(endsAt.isAfter(startsAt)) { "busy-time window must have positive duration" }
        val href = requireCalendarHref(calendarHref)
        return buildString {
            append(BUSY_TIME_PATH)
            append("?calendar=")
            append(encode(href))
            append("&starts_at=")
            append(encode(startsAt.toString()))
            append("&ends_at=")
            append(encode(endsAt.toString()))
        }
    }

    fun readiness(): CalendarReadContractSnapshot = CalendarReadContractSnapshot(
        eventListing = CalendarReadContractState.SOURCE_READY,
        busyTime = CalendarReadContractState.SOURCE_READY,
        responseAcceptance = CalendarReadContractState.SOURCE_READY,
        nativeIdentityBindingContract = CalendarReadContractState.SOURCE_READY,
        nativeIdentitySession = CalendarReadContractState.IDENTITY_BLOCKED,
        networkTransport = CalendarReadContractState.TRANSPORT_BLOCKED,
    )

    private fun requireCalendarHref(value: String): String {
        require(value.isNotBlank()) { "calendar href must be non-blank" }
        require(value.length <= MAX_CALENDAR_HREF_LENGTH) {
            "calendar href exceeds $MAX_CALENDAR_HREF_LENGTH characters"
        }
        require(value.none(Char::isISOControl)) { "calendar href must not contain control characters" }
        require(value == value.trim()) { "calendar href must already be canonical; trimming is not allowed" }
        require(value.startsWith('/')) { "calendar href must be a server-relative path" }
        require(!value.startsWith("//")) { "calendar href must not be a scheme-relative authority" }
        return value
    }

    private fun requireTimezone(value: String): String {
        require(value.isNotBlank()) { "timezone must be non-blank" }
        require(value.length <= MAX_TIMEZONE_LENGTH) { "timezone exceeds $MAX_TIMEZONE_LENGTH characters" }
        require(value.none(Char::isISOControl)) { "timezone must not contain control characters" }
        require(value == value.trim()) { "timezone must already be canonical; trimming is not allowed" }
        return value
    }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20")
}
