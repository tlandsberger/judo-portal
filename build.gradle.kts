plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.spring) apply false
    alias(libs.plugins.kotlin.jpa) apply false
    alias(libs.plugins.spring.boot) apply false
    alias(libs.plugins.spring.dependency.management) apply false
    alias(libs.plugins.spotless) apply false
}

// Einheitlicher Code-Stil: ktlint über Spotless für alle Module, Regeln in .editorconfig.
// `./gradlew spotlessApply` formatiert, `check` prüft.
val spotlessPluginId = libs.plugins.spotless.get().pluginId
val ktlintVersion = libs.versions.ktlint.get()

subprojects {
    apply(plugin = spotlessPluginId)
    extensions.configure<com.diffplug.gradle.spotless.SpotlessExtension> {
        kotlin {
            target("src/**/*.kt")
            ktlint(ktlintVersion)
        }
        kotlinGradle {
            target("*.gradle.kts")
            ktlint(ktlintVersion)
        }
    }
}
