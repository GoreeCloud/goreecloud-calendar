package com.goreecloud.calendar

import android.content.res.Configuration
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalConfiguration

/** Repository-local Android adoption boundary for current Stable GLAZE UI V1.4. */
object GlazeCalendarContract {
    const val VERSION = "1.4.0"
    const val REFERENCE_REVISION = "84cb3db4884042f0fa25ed6d475a127fb110f596"
    const val ADOPTION_STATE = "ADOPTION_IN_PROGRESS"

    const val OPTICAL_ENGINE_ACCEPTED = false
    const val REDUCED_TRANSPARENCY_ACCEPTED = false
    const val INCREASED_CONTRAST_ACCEPTED = false
    const val PHYSICAL_DEVICE_ACCEPTED = false
    const val HUMAN_VISUAL_ACCEPTED = false
}

@Composable
fun GlazeCalendarTheme(content: @Composable () -> Unit) {
    val dark = (LocalConfiguration.current.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    MaterialTheme(
        colorScheme = if (dark) darkColorScheme() else lightColorScheme(),
        content = content,
    )
}
