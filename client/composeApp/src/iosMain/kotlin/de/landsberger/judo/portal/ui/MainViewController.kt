package de.landsberger.judo.portal.ui

import androidx.compose.ui.window.ComposeUIViewController
import platform.UIKit.UIViewController

/** Wird von der iOS-App (Xcode-Projekt, folgt in Schritt 5) eingebunden. */
@Suppress("ktlint:standard:function-naming")
fun MainViewController(): UIViewController = ComposeUIViewController { App() }
