package de.landsberger.judo.portal.backend.members.internal.access

import de.landsberger.judo.portal.backend.members.internal.domain.Member
import jakarta.persistence.Entity
import jakarta.persistence.EnumType
import jakarta.persistence.Enumerated
import jakarta.persistence.FetchType
import jakarta.persistence.Id
import jakarta.persistence.JoinColumn
import jakarta.persistence.ManyToOne
import jakarta.persistence.Table
import org.hibernate.annotations.CreationTimestamp
import org.springframework.data.jpa.repository.JpaRepository
import java.time.Instant
import java.util.UUID

/** Verknüpfung eines Keycloak-Kontos mit einem Mitglied. */
@Entity
@Table(name = "member_access")
class MemberAccess(
    @Id
    val id: UUID = UUID.randomUUID(),
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "member_id")
    val member: Member,
    /** Keycloak-User-ID (`sub`). */
    val accountId: String,
    @Enumerated(EnumType.STRING)
    val relation: AccessRelation,
    /** Stand bei der Einladung, zur Anzeige ohne Keycloak-Aufruf. */
    val accountEmail: String,
    val accountName: String,
) {
    @CreationTimestamp
    var createdAt: Instant? = null
}

interface MemberAccessRepository : JpaRepository<MemberAccess, UUID> {
    fun findByMemberIdOrderByCreatedAt(memberId: UUID): List<MemberAccess>

    fun findByAccountId(accountId: String): List<MemberAccess>

    fun findByMemberIdAndAccountId(
        memberId: UUID,
        accountId: String,
    ): MemberAccess?

    fun existsByMemberIdAndRelation(
        memberId: UUID,
        relation: AccessRelation,
    ): Boolean

    fun existsByAccountIdAndRelation(
        accountId: String,
        relation: AccessRelation,
    ): Boolean
}
