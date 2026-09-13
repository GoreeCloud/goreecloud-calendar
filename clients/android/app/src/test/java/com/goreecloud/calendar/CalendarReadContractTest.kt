package com.goreecloud.calendar

import java.time.LocalDate
import java.time.OffsetDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class CalendarReadContractTest {
    @Test
    fun eventListingBuildsOnlyTheExistingRelativeEndpoint() {
        assertEquals(
            "/api/v1/events?calendar=%2Fusers%2Falice%2Fcalendar%2F&anchor=2026-09-13&view=week&timezone=America%2FChicago",
            CalendarReadContract.eventsPath(
                calendarHref = "/users/alice/calendar/",
                anchor = LocalDate.parse("2026-09-13"),
                view = CalendarViewMode.WEEK,
                timezone = "America/Chicago",
            ),
        )
    }

    @Test
    fun busyTimeRequiresPositiveTimezoneAwareWindow() {
        val start = OffsetDateTime.parse("2026-09-13T09:00:00-05:00")
        val end = OffsetDateTime.parse("2026-09-13T10:30:00-05:00")

        assertEquals(
            "/api/v1/busy-time?calendar=%2Fusers%2Falice%2Fcalendar%2F&starts_at=2026-09-13T09%3A00-05%3A00&ends_at=2026-09-13T10%3A30-05%3A00",
            CalendarReadContract.busyTimePath("/users/alice/calendar/", start, end),
        )
        assertThrows(IllegalArgumentException::class.java) {
            CalendarReadContract.busyTimePath("/users/alice/calendar/", end, start)
        }
    }

    @Test
    fun absoluteAndSchemeRelativeCalendarAuthoritiesAreRejected() {
        listOf(
            "https://dav.example.test/users/alice/calendar/",
            "//dav.example.test/users/alice/calendar/",
        ).forEach { value ->
            assertThrows(IllegalArgumentException::class.java) {
                CalendarReadContract.eventsPath(value, LocalDate.parse("2026-09-13"))
            }
        }
    }

    @Test
    fun malformedCalendarAndTimezoneInputsFailClosed() {
        listOf("", "   ", " /users/alice/calendar/", "/users/alice/calendar/\n").forEach { value ->
            assertThrows(IllegalArgumentException::class.java) {
                CalendarReadContract.eventsPath(value, LocalDate.parse("2026-09-13"))
            }
        }
        listOf("", " UTC", "America/Chicago\n", "a".repeat(129)).forEach { timezone ->
            assertThrows(IllegalArgumentException::class.java) {
                CalendarReadContract.eventsPath(
                    calendarHref = "/users/alice/calendar/",
                    anchor = LocalDate.parse("2026-09-13"),
                    timezone = timezone,
                )
            }
        }
    }

    @Test
    fun allSupportedViewModesMatchTheServerContract() {
        assertEquals(
            listOf("month", "week", "day", "agenda"),
            CalendarViewMode.entries.map { it.wireValue },
        )
    }

    @Test
    fun identityContractCanBeSourceReadyWithoutClaimingLiveSessionOrTransport() {
        val readiness = CalendarReadContract.readiness()
        assertEquals(CalendarReadContractState.SOURCE_READY, readiness.eventListing)
        assertEquals(CalendarReadContractState.SOURCE_READY, readiness.busyTime)
        assertEquals(CalendarReadContractState.SOURCE_READY, readiness.nativeIdentityBindingContract)
        assertEquals(CalendarReadContractState.IDENTITY_BLOCKED, readiness.nativeIdentitySession)
        assertEquals(CalendarReadContractState.TRANSPORT_BLOCKED, readiness.networkTransport)
    }
}
