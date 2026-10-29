package de.landsberger.judo.portal.backend.members.internal.domain

import org.springframework.data.jpa.repository.JpaRepository
import java.util.UUID

interface MemberRepository : JpaRepository<Member, UUID> {
    fun findByMemberNumber(memberNumber: String): Member?
}
