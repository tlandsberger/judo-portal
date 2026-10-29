package de.landsberger.judo.portal.backend.members.internal.domain

import com.fasterxml.jackson.annotation.JsonValue

/** Art der Mitgliedschaft. „Ausgetreten“ ist kein Typ, sondern ergibt sich aus dem Austrittsdatum. */
enum class MembershipType {
    ACTIVE,
    PASSIVE,
    ;

    @get:JsonValue
    val json: String get() = name.lowercase()
}
