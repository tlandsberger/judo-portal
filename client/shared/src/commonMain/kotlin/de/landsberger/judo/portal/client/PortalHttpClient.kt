package de.landsberger.judo.portal.client

import io.ktor.client.HttpClient
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

/**
 * Erzeugt den HTTP-Client für die Portal-API. Die Engine (OkHttp, Darwin, Fetch)
 * wählt Ktor automatisch passend zur Plattform. Auth kommt in Schritt 5 dazu.
 */
fun createPortalHttpClient(baseUrl: String): HttpClient =
    HttpClient {
        expectSuccess = true
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
        defaultRequest {
            url(baseUrl)
        }
    }
