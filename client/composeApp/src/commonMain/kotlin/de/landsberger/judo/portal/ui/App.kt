package de.landsberger.judo.portal.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

const val APP_NAME = "WTSV Judo"

/** Einstiegspunkt der gemeinsamen UI für Android, iOS und Web. */
@Composable
fun App() {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(text = APP_NAME, style = MaterialTheme.typography.headlineLarge)
                Text(text = "Vereinsportal – im Aufbau", style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}
