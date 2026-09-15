package com.goreecloud.calendar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class GlazeCalendarContractTest {
    @Test
    fun currentStableGlazeReferenceIsPinned() {
        assertEquals("1.4.1", GlazeCalendarContract.VERSION)
        assertEquals(
            "4fab9da0fad2e5c974e0e66ec88632c61745751c",
            GlazeCalendarContract.REFERENCE_REVISION,
        )
        assertEquals("1.4.0", GlazeCalendarContract.ROLLBACK_VERSION)
        assertEquals("ADOPTION_IN_PROGRESS", GlazeCalendarContract.ADOPTION_STATE)
    }

    @Test
    fun sharedStableQualificationDoesNotCreateCalendarAcceptance() {
        assertFalse(GlazeCalendarContract.OPTICAL_ENGINE_ACCEPTED)
        assertFalse(GlazeCalendarContract.REDUCED_TRANSPARENCY_ACCEPTED)
        assertFalse(GlazeCalendarContract.INCREASED_CONTRAST_ACCEPTED)
        assertFalse(GlazeCalendarContract.PHYSICAL_DEVICE_ACCEPTED)
        assertFalse(GlazeCalendarContract.HUMAN_VISUAL_ACCEPTED)
    }
}
