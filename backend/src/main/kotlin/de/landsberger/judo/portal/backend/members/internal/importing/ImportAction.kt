package de.landsberger.judo.portal.backend.members.internal.importing

import com.fasterxml.jackson.annotation.JsonValue

/** Was der Import mit einer Zeile macht. */
enum class ImportAction {
    CREATE,
    UPDATE,
    UNCHANGED,
    ERROR,
    ;

    @get:JsonValue
    val json: String get() = name.lowercase()
}
