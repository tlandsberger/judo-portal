package de.landsberger.judo.portal.backend.members.internal.domain

import com.fasterxml.jackson.annotation.JsonValue

/** Geschlecht laut Mitgliedsantrag, gebraucht u. a. für die Bestandsmeldung an den Landessportbund. */
enum class Gender {
    FEMALE,
    MALE,
    DIVERSE,
    ;

    @get:JsonValue
    val json: String get() = name.lowercase()
}
