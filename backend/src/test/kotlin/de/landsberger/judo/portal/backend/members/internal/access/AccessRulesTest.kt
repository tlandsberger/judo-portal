package de.landsberger.judo.portal.backend.members.internal.access

import org.junit.jupiter.api.Test
import java.time.LocalDate
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AccessRulesTest {
    private val today = LocalDate.of(2026, 10, 29)

    @Test
    fun `own access from the 14th birthday`() {
        assertFalse(AccessRules.mayHaveOwnAccess(LocalDate.of(2012, 10, 30), today))
        assertTrue(AccessRules.mayHaveOwnAccess(LocalDate.of(2012, 10, 29), today))
    }

    @Test
    fun `parents see their child until the day before the 18th birthday`() {
        val turns18Tomorrow = LocalDate.of(2008, 10, 30)
        val turns18Today = LocalDate.of(2008, 10, 29)
        assertTrue(AccessRules.isVisible(AccessRelation.GUARDIAN, turns18Tomorrow, today))
        assertFalse(AccessRules.isVisible(AccessRelation.GUARDIAN, turns18Today, today))
        assertTrue(AccessRules.isVisible(AccessRelation.SELF, turns18Today, today))
    }

    @Test
    fun `leap day birthdays count from the 1st of March in common years`() {
        val leapDay = LocalDate.of(2012, 2, 29)
        assertFalse(AccessRules.mayHaveOwnAccess(leapDay, LocalDate.of(2026, 2, 28)))
        assertTrue(AccessRules.mayHaveOwnAccess(leapDay, LocalDate.of(2026, 3, 1)))
    }
}
