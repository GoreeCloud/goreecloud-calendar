package com.goreecloud.calendar

import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CalendarIdentityBindingTest {
    private val now = Instant.parse("2026-09-13T18:00:00Z")
    private val expectation = CalendarIdentityExpectation(principalId = "user-42")

    private fun proof(
        principalId: String = expectation.principalId,
        audience: String = CalendarIdentityExpectation.ANDROID_CALENDAR_AUDIENCE,
        issuedAt: Instant = now.minusSeconds(60),
        expiresAt: Instant = now.plusSeconds(600),
    ) = CalendarIdentityProof(principalId, audience, issuedAt, expiresAt)

    @Test
    fun canonicalIdentityContractCandidateIsPinnedExactly() {
        assertEquals(
            "goreecloud.identity.native-application-session/v1",
            CalendarIdentityContractReference.SCHEMA,
        )
        assertEquals(
            "62ad109809f2e479cf71a6327ffd0d4537a6b3df",
            CalendarIdentityContractReference.CANDIDATE_REVISION,
        )
    }

    @Test fun missingProofFailsClosed() {
        assertEquals(CalendarIdentityBindingDecision.MissingProof, CalendarIdentityBindingPolicy.evaluate(null, expectation, now))
    }

    @Test fun exactPrincipalAndAudienceCanBind() {
        val decision = CalendarIdentityBindingPolicy.evaluate(proof(), expectation, now)
        assertTrue(decision is CalendarIdentityBindingDecision.Bound)
        assertEquals("user-42", (decision as CalendarIdentityBindingDecision.Bound).principalId)
    }

    @Test fun malformedIdentityIsRejectedRatherThanNormalized() {
        assertEquals(CalendarIdentityBindingDecision.InvalidProof, CalendarIdentityBindingPolicy.evaluate(proof(principalId = " user-42"), expectation, now))
        assertEquals(CalendarIdentityBindingDecision.InvalidProof, CalendarIdentityBindingPolicy.evaluate(proof(audience = "goreecloud-calendar-android\n"), expectation, now))
    }

    @Test fun principalAndAudienceMismatchFailIndependently() {
        assertEquals(CalendarIdentityBindingDecision.PrincipalMismatch, CalendarIdentityBindingPolicy.evaluate(proof(principalId = "user-41"), expectation, now))
        assertEquals(CalendarIdentityBindingDecision.AudienceMismatch, CalendarIdentityBindingPolicy.evaluate(proof(audience = "goreecloud-contacts-android"), expectation, now))
    }

    @Test fun lifetimeChecksFailClosed() {
        assertEquals(CalendarIdentityBindingDecision.InvalidProof, CalendarIdentityBindingPolicy.evaluate(proof(issuedAt = now, expiresAt = now), expectation, now))
        assertEquals(CalendarIdentityBindingDecision.NotYetValid, CalendarIdentityBindingPolicy.evaluate(proof(issuedAt = now.plusSeconds(1), expiresAt = now.plusSeconds(600)), expectation, now))
        assertEquals(CalendarIdentityBindingDecision.Expired, CalendarIdentityBindingPolicy.evaluate(proof(expiresAt = now), expectation, now))
    }

    @Test fun malformedExpectationCannotGrantAuthority() {
        assertEquals(CalendarIdentityBindingDecision.InvalidExpectation, CalendarIdentityBindingPolicy.evaluate(proof(), expectation.copy(principalId = "user-42 "), now))
    }
}
