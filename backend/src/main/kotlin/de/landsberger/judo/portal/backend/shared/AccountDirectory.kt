package de.landsberger.judo.portal.backend.shared

/** Ein Benutzerkonto im Identity Provider (Keycloak), wie es die Fachmodule sehen. */
data class Account(
    /** Keycloak-User-ID, entspricht `sub` im Token bzw. [CurrentUser.subject]. */
    val id: String,
    val email: String,
    val firstName: String?,
    val lastName: String?,
    /** Erst nach dem Klick auf den Einladungslink bestätigt; vorher gilt das Konto als „eingeladen“. */
    val emailVerified: Boolean,
) {
    val displayName: String get() = listOfNotNull(firstName, lastName).joinToString(" ").ifBlank { email }
}

/**
 * Zugriff auf die Benutzerkonten (ADR 0009). Das Backend legt Konten nur für Einladungen an und vergibt dabei
 * höchstens die Rolle `member`; alle anderen Rollen pflegt der Administrator in Keycloak.
 */
interface AccountDirectory {
    fun findByEmail(email: String): Account?

    fun find(id: String): Account?

    fun create(
        email: String,
        firstName: String,
        lastName: String,
    ): Account

    /** Mail mit Link zum Passwort-Setzen und E-Mail-Bestätigen; danach geht es ins Portal. */
    fun sendInvitation(id: String)

    fun grantRole(
        id: String,
        role: Role,
    )

    fun revokeRole(
        id: String,
        role: Role,
    )
}
