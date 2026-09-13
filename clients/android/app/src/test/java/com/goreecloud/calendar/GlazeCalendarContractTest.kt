package com.goreecloud.calendar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class GlazeCalendarContractTest {
    @Test
    fun currentStableGlazeReferenceIsPinned() {
        assertEquals("1.4.0", GlazeCalendarContract.VERSION)
        assertEquals(
            "84cb3db4884042f0fa25ed6d475a127fb110f596",
            GlazeCalendarContract.REFERENCE_REVISION,
        )
        assertEquals("ADOPTION_IN_PROGRESS", GlazeCalendarContract.ADOPTION_STATE)
    }

    @Test
    fun opticalAndHumanAcceptanceRemainFailClosed() {
        assertFalse(GlazeCalendarContract.OPTICAL_ENGINE_ACCEPTED)
        assertFalse(GlazeCalendarContract.REDUCED_TRANSPARENCY_ACCEPTED)
        assertFalse(GlazeCalendarContract.INCREASED_CONTRAST_ACCEPTED)
        assertFalse(GlazeCalendarContract.PHYSICAL_DEVICE_ACCEPTED)
        assertFalse(GlazeCalendarContract.HUMAN_VISUAL_ACCEPTED)
    }
}
