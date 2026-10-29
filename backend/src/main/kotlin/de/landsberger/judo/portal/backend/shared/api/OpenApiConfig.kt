package de.landsberger.judo.portal.backend.shared.api

import de.landsberger.judo.portal.backend.shared.CurrentUser
import io.swagger.v3.oas.models.Components
import io.swagger.v3.oas.models.OpenAPI
import io.swagger.v3.oas.models.info.Info
import io.swagger.v3.oas.models.security.SecurityRequirement
import io.swagger.v3.oas.models.security.SecurityScheme
import io.swagger.v3.oas.models.servers.Server
import org.springdoc.core.customizers.OpenApiCustomizer
import org.springdoc.core.utils.SpringDocUtils
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

/**
 * Beschreibung der Portal-API. Sie ist der Vertrag mit der PWA (ADR 0007) und liegt als
 * `api/openapi.json` im Repo; `OpenApiContractIT` hält beides synchron.
 */
@Configuration
class OpenApiConfig {
    init {
        // CurrentUser kommt aus dem Token, nicht aus dem Request.
        SpringDocUtils.getConfig().addRequestWrapperToIgnore(CurrentUser::class.java)
    }

    @Bean
    fun portalOpenApi(): OpenAPI =
        OpenAPI()
            .info(Info().title("WTSV Judo – Portal-API").version("v1"))
            // Relativer Server: PWA und API laufen auf demselben Origin (Caddy bzw. Dev-Proxy).
            .servers(listOf(Server().url("/")))
            .components(
                Components().addSecuritySchemes(
                    BEARER,
                    SecurityScheme()
                        .type(SecurityScheme.Type.HTTP)
                        .scheme("bearer")
                        .bearerFormat("JWT")
                        .description("Access-Token von Keycloak (Realm judo, Audience judo-portal-api)"),
                ),
            ).addSecurityItem(SecurityRequirement().addList(BEARER))

    /**
     * Alle nicht-nullbaren Felder als `required` markieren. So entsprechen die generierten
     * TypeScript-Typen den Kotlin-Typen: `String` → Pflichtfeld, `String?` → `string | null`.
     */
    @Bean
    fun requiredNonNullableProperties(): OpenApiCustomizer =
        OpenApiCustomizer { openApi ->
            openApi.components?.schemas?.values?.forEach { schema ->
                val properties = schema.properties ?: return@forEach
                schema.required =
                    properties
                        .filterValues { property ->
                            property.types?.contains("null") != true &&
                                property.nullable != true
                        }.keys
                        .sorted()
            }
        }

    private companion object {
        const val BEARER = "bearer"
    }
}
