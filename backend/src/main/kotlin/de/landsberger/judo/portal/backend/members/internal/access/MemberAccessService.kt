package de.landsberger.judo.portal.backend.members.internal.access

import de.landsberger.judo.portal.backend.members.internal.domain.Member
import de.landsberger.judo.portal.backend.members.internal.domain.MemberService
import de.landsberger.judo.portal.backend.shared.AccountDirectory
import de.landsberger.judo.portal.backend.shared.ConflictException
import de.landsberger.judo.portal.backend.shared.InvalidInputException
import de.landsberger.judo.portal.backend.shared.NotFoundException
import de.landsberger.judo.portal.backend.shared.Role
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.time.Clock
import java.time.LocalDate
import java.util.UUID

/** Ein Zugang mit seinem aktuellen Zustand. */
data class AccessView(
    val access: MemberAccess,
    val status: AccessStatus,
)

/** Ergebnis einer Einladung: neues Konto mit Mail oder Verknüpfung eines bestehenden, aktiven Kontos. */
data class InvitationResult(
    val access: AccessView,
    val invitationSent: Boolean,
)

/**
 * Einladen, Verknüpfen und Entfernen von Zugängen sowie die eigene Sicht der Mitglieder und Eltern.
 * Wer verwalten darf, prüft der Controller; die Altersregeln stehen in [AccessRules].
 */
@Service
@Transactional
class MemberAccessService(
    private val members: MemberService,
    private val accesses: MemberAccessRepository,
    private val directory: AccountDirectory,
    private val clock: Clock,
) {
    @Transactional(readOnly = true)
    fun list(memberId: UUID): List<AccessView> {
        val member = members.get(memberId)
        return accesses.findByMemberIdOrderByCreatedAt(member.id).map { view(it) }
    }

    fun invite(
        memberId: UUID,
        relation: AccessRelation,
        email: String,
        firstName: String?,
        lastName: String?,
    ): InvitationResult {
        val member = members.get(memberId)
        val address = email.trim().lowercase()
        checkAge(member, relation)
        if (relation == AccessRelation.SELF && accesses.existsByMemberIdAndRelation(member.id, AccessRelation.SELF)) {
            throw ConflictException("Das Mitglied hat bereits einen eigenen Zugang.", field = "relation")
        }
        val (first, last) =
            when (relation) {
                AccessRelation.SELF -> {
                    member.firstName to member.lastName
                }

                AccessRelation.GUARDIAN -> {
                    required(firstName, "firstName", "Bitte den Vornamen angeben.") to
                        required(lastName, "lastName", "Bitte den Nachnamen angeben.")
                }
            }

        val account = directory.findByEmail(address) ?: directory.create(address, first, last)
        if (accesses.findByMemberIdAndAccountId(member.id, account.id) != null) {
            throw ConflictException("Dieses Konto ist bereits mit dem Mitglied verknüpft.", field = "email")
        }
        if (relation == AccessRelation.SELF && accesses.existsByAccountIdAndRelation(account.id, AccessRelation.SELF)) {
            throw ConflictException(
                "Dieses Konto ist bereits einem anderen Mitglied als eigener Zugang zugeordnet.",
                field = "email",
            )
        }
        val access =
            accesses.saveAndFlush(
                MemberAccess(
                    member = member,
                    accountId = account.id,
                    relation = relation,
                    accountEmail = account.email,
                    accountName = account.displayName,
                ),
            )
        if (relation == AccessRelation.SELF) {
            directory.grantRole(account.id, Role.MEMBER)
        }
        // Auch ein früher angelegtes, nie bestätigtes Konto bekommt (erneut) eine Einladung.
        val sendMail = !account.emailVerified
        if (sendMail) {
            directory.sendInvitation(account.id)
        }
        val status = if (sendMail) AccessStatus.INVITED else AccessStatus.ACTIVE
        return InvitationResult(AccessView(access, status), invitationSent = sendMail)
    }

    fun resend(
        memberId: UUID,
        accessId: UUID,
    ) {
        val access = find(memberId, accessId)
        val account = directory.find(access.accountId) ?: throw NotFoundException("Das Konto gibt es nicht mehr.")
        if (account.emailVerified) {
            throw ConflictException("Der Zugang ist bereits aktiv, eine Einladung ist nicht nötig.")
        }
        directory.sendInvitation(account.id)
    }

    fun remove(
        memberId: UUID,
        accessId: UUID,
    ) {
        val access = find(memberId, accessId)
        accesses.delete(access)
        if (access.relation == AccessRelation.SELF && directory.find(access.accountId) != null) {
            directory.revokeRole(access.accountId, Role.MEMBER)
        }
    }

    /** Mitglieder, die das Konto sehen darf: sich selbst und Kinder unter 18. */
    @Transactional(readOnly = true)
    fun visibleTo(accountId: String): List<Pair<AccessRelation, Member>> =
        accesses
            .findByAccountId(accountId)
            .filter { AccessRules.isVisible(it.relation, it.member.birthDate, today()) }
            .sortedWith(compareBy({ it.relation.ordinal }, { it.member.lastName }, { it.member.firstName }))
            .map { it.relation to it.member }

    @Transactional(readOnly = true)
    fun visibleMember(
        accountId: String,
        memberId: UUID,
    ): Pair<AccessRelation, Member> =
        visibleTo(accountId).firstOrNull { it.second.id == memberId }
            ?: throw NotFoundException("Das Mitglied gibt es nicht oder du darfst es nicht sehen.")

    private fun checkAge(
        member: Member,
        relation: AccessRelation,
    ) {
        val today = today()
        when (relation) {
            AccessRelation.SELF -> {
                if (!AccessRules.mayHaveOwnAccess(member.birthDate, today)) {
                    throw InvalidInputException(
                        "relation",
                        "Einen eigenen Zugang gibt es erst ab ${AccessRules.SELF_MIN_AGE} Jahren.",
                    )
                }
            }

            AccessRelation.GUARDIAN -> {
                if (!AccessRules.isMinor(member.birthDate, today)) {
                    throw InvalidInputException("relation", "Erziehungsberechtigte gibt es nur für Minderjährige.")
                }
            }
        }
    }

    private fun view(access: MemberAccess): AccessView {
        val status =
            when {
                !AccessRules.isVisible(access.relation, access.member.birthDate, today()) -> {
                    AccessStatus.EXPIRED
                }

                else -> {
                    when (directory.find(access.accountId)?.emailVerified) {
                        null -> AccessStatus.MISSING
                        true -> AccessStatus.ACTIVE
                        false -> AccessStatus.INVITED
                    }
                }
            }
        return AccessView(access, status)
    }

    private fun find(
        memberId: UUID,
        accessId: UUID,
    ): MemberAccess =
        accesses.findById(accessId).orElse(null)?.takeIf { it.member.id == memberId }
            ?: throw NotFoundException("Den Zugang gibt es nicht.")

    private fun required(
        value: String?,
        field: String,
        message: String,
    ): String = value?.trim()?.takeIf { it.isNotEmpty() } ?: throw InvalidInputException(field, message)

    private fun today(): LocalDate = LocalDate.now(clock)
}
