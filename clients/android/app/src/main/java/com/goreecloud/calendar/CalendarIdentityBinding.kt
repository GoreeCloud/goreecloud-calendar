package com.goreecloud.calendar

import java.time.Instant

object CalendarIdentityContractReference {
    const val SCHEMA = "goreecloud.identity.native-application-session/v1"
    const val CANDIDATE_REVISION = "62ad109809f2e479cf71a6327ffd0d4537a6b3df"
}

/**
 * Non-secret identity proof metadata required before a future native Calendar session may activate.
 * No token, cookie, password, CalDAV credential, refresh secret, or transport is modeled here.
 */
data class CalendarIdentityProof(
    val principalId: String,
    val audience: String,
    val issuedAt: Instant,
    val expiresAt: Instant,
)

data class CalendarIdentityExpectation(
    val principalId: String,
    val audience: String = ANDROID_CALENDAR_AUDIENCE,
) {
    companion object {
        const val ANDROID_CALENDAR_AUDIENCE = "goreecloud-calendar-android"
    }
}

sealed interface CalendarIdentityBindingDecision {
    data class Bound(
        val principalId: String,
        val expiresAt: Instant,
    ) : CalendarIdentityBindingDecision

    data object MissingProof : CalendarIdentityBindingDecision
    data object InvalidExpectation : CalendarIdentityBindingDecision
    data object InvalidProof : CalendarIdentityBindingDecision
    data object PrincipalMismatch : CalendarIdentityBindingDecision
    data object AudienceMismatch : CalendarIdentityBindingDecision
    data object NotYetValid : CalendarIdentityBindingDecision
    data object Expired : CalendarIdentityBindingDecision
}

/**
 * Pure, fail-closed metadata policy aligned to the pinned GoreeCloud Identity native-session
 * source contract candidate. A Bound result does not authenticate, enable transport, or authorize
 * event access.
 */
object CalendarIdentityBindingPolicy {
    fun evaluate(
        proof: CalendarIdentityProof?,
        expectation: CalendarIdentityExpectation,
        now: Instant,
    ): CalendarIdentityBindingDecision {
        if (!isExactIdentity(expectation.principalId) || !isExactIdentity(expectation.audience)) {
            return CalendarIdentityBindingDecision.InvalidExpectation
        }

        proof ?: return CalendarIdentityBindingDecision.MissingProof

        if (!isExactIdentity(proof.principalId) ||
            !isExactIdentity(proof.audience) ||
            !proof.issuedAt.isBefore(proof.expiresAt)
        ) {
            return CalendarIdentityBindingDecision.InvalidProof
        }

        if (proof.principalId != expectation.principalId) {
            return CalendarIdentityBindingDecision.PrincipalMismatch
        }
        if (proof.audience != expectation.audience) {
            return CalendarIdentityBindingDecision.AudienceMismatch
        }
        if (now.isBefore(proof.issuedAt)) {
            return CalendarIdentityBindingDecision.NotYetValid
        }
        if (!now.isBefore(proof.expiresAt)) {
            return CalendarIdentityBindingDecision.Expired
        }

        return CalendarIdentityBindingDecision.Bound(
            principalId = proof.principalId,
            expiresAt = proof.expiresAt,
        )
    }

    private fun isExactIdentity(value: String): Boolean =
        value.isNotBlank() && value == value.trim() && value.none(Char::isISOControl)
}
