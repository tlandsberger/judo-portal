package de.landsberger.judo.portal.api

import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals

class MeResponseTest {
    @Test
    fun rolesAreSerializedWithKeycloakNames() {
        val me = MeResponse(subject = "42", displayName = "Jigoro Kano", roles = setOf(Role.TRAINER))

        val json = Json.encodeToString(me)

        assertEquals("""{"subject":"42","displayName":"Jigoro Kano","roles":["trainer"]}""", json)
        assertEquals(me, Json.decodeFromString<MeResponse>(json))
    }
}
