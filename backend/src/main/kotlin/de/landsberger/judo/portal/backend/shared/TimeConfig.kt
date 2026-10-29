package de.landsberger.judo.portal.backend.shared

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import java.time.Clock
import java.time.ZoneId

/** Fachliches „heute“ gilt in der Zeitzone des Vereins; Tests können die [Clock] ersetzen. */
@Configuration
class TimeConfig {
    @Bean
    fun clock(): Clock = Clock.system(ZoneId.of("Europe/Berlin"))
}
