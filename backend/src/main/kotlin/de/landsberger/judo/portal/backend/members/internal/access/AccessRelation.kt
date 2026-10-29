package de.landsberger.judo.portal.backend.members.internal.access

import com.fasterxml.jackson.annotation.JsonValue

/** Wie ein Konto mit einem Mitglied verbunden ist. */
enum class AccessRelation {
    /** Das Mitglied selbst (ab 14 Jahren). */
    SELF,

    /** Erziehungsberechtigte Person eines minderjährigen Mitglieds. */
    GUARDIAN,
    ;

    @get:JsonValue
    val json: String get() = name.lowercase()
}

/** Zustand eines Zugangs aus Sicht der Verwaltung. */
enum class AccessStatus {
    /** Einladung verschickt, Link noch nicht genutzt. */
    INVITED,
    ACTIVE,

    /** Elternzugang, dessen Kind volljährig ist – sieht nichts mehr. */
    EXPIRED,

    /** Das Konto gibt es in Keycloak nicht mehr. */
    MISSING,
    ;

    @get:JsonValue
    val json: String get() = name.lowercase()
}
