package de.landsberger.judo.portal.backend.shared.security

import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity
import org.springframework.security.config.annotation.web.builders.HttpSecurity
import org.springframework.security.config.annotation.web.invoke
import org.springframework.security.config.http.SessionCreationPolicy
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken
import org.springframework.security.web.SecurityFilterChain

/**
 * Das Backend ist ein reiner OAuth2 Resource Server: Keycloak authentifiziert, das Backend prüft
 * Signatur, Issuer und Audience des Bearer-Tokens (application.yml) und autorisiert (ADR 0003, 0006).
 */
@Configuration
@EnableMethodSecurity
class SecurityConfig {
    @Bean
    fun securityFilterChain(http: HttpSecurity): SecurityFilterChain {
        http {
            // Keine Sessions und keine Cookies: CSRF-Schutz ist bei reinen Bearer-Tokens nicht nötig.
            csrf { disable() }
            sessionManagement { sessionCreationPolicy = SessionCreationPolicy.STATELESS }
            authorizeHttpRequests {
                authorize("/actuator/health", permitAll)
                authorize("/actuator/health/**", permitAll)
                authorize("/error", permitAll)
                authorize("/api/**", authenticated)
                authorize(anyRequest, denyAll)
            }
            oauth2ResourceServer {
                jwt {
                    jwtAuthenticationConverter =
                        { jwt ->
                            JwtAuthenticationToken(jwt, KeycloakRoles.authorities(jwt), KeycloakRoles.subject(jwt))
                        }
                }
            }
        }
        return http.build()
    }
}
