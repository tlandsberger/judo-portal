package de.landsberger.judo.portal.backend.members.internal.importing

import de.landsberger.judo.portal.backend.shared.InvalidInputException
import org.apache.commons.csv.CSVFormat
import java.io.IOException
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction

/** Eine Datenzeile; [line] ist die Zeilennummer wie in Excel (Kopfzeile = 1). */
data class CsvRow(
    val line: Long,
    private val values: Map<String, String>,
) {
    /** Wert der Spalte (Überschrift normalisiert, siehe [CsvReader.normalize]); leer, wenn es sie nicht gibt. */
    operator fun get(column: String): String = values[column].orEmpty()
}

data class CsvTable(
    val columns: Set<String>,
    val rows: List<CsvRow>,
)

/**
 * Liest CSV-Exporte aus Excel. Excel speichert je nach Variante UTF-8 (mit BOM, „CSV UTF-8“) oder
 * Windows-1252 („CSV (Trennzeichen-getrennt)“), deutsch meist mit Semikolon. Beides wird erkannt.
 */
object CsvReader {
    private val UTF8_BOM = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())
    private val WINDOWS_1252 = Charset.forName("windows-1252")

    fun read(bytes: ByteArray): CsvTable {
        val text = decode(bytes)
        val header = text.lineSequence().firstOrNull { it.isNotBlank() } ?: throw invalid("Die Datei ist leer.")
        val delimiter = if (header.count { it == ';' } >= header.count { it == ',' }) ';' else ','
        val format =
            CSVFormat.DEFAULT
                .builder()
                .setDelimiter(delimiter)
                .setHeader()
                .setSkipHeaderRecord(true)
                .setIgnoreEmptyLines(true)
                .setAllowMissingColumnNames(true)
                .setTrim(true)
                .get()
        try {
            format.parse(text.reader()).use { parser ->
                val names = parser.headerNames
                val columns = names.map(::normalize).toSet()
                val rows =
                    parser.records
                        .map { record ->
                            val values =
                                names.indices
                                    .filter { it < record.size() }
                                    .associate { normalize(names[it]) to record.get(it) }
                            CsvRow(line = record.recordNumber + 1, values = values)
                        }.filter { row -> columns.any { row[it].isNotEmpty() } }
                return CsvTable(columns, rows)
            }
        } catch (e: IOException) {
            throw invalid("Die Datei ist keine gültige CSV-Datei (${e.message}).")
        } catch (e: IllegalArgumentException) {
            throw invalid("Die Datei ist keine gültige CSV-Datei (${e.message}).")
        } catch (e: IllegalStateException) {
            throw invalid("Die Datei ist keine gültige CSV-Datei (${e.message}).")
        }
    }

    /** Spaltenüberschrift vergleichbar machen: klein, ohne überzählige Leerzeichen. */
    fun normalize(header: String): String =
        header
            .trim()
            .lowercase()
            .replace(Regex("\\s+"), " ")

    private fun decode(bytes: ByteArray): String {
        if (bytes.size >= 3 && bytes.copyOfRange(0, 3).contentEquals(UTF8_BOM)) {
            return String(bytes, 3, bytes.size - 3, Charsets.UTF_8)
        }
        return try {
            Charsets.UTF_8
                .newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes))
                .toString()
        } catch (_: CharacterCodingException) {
            String(bytes, WINDOWS_1252)
        }
    }

    private fun invalid(message: String) = InvalidInputException("file", message)
}
