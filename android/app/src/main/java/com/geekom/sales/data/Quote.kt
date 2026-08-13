package com.geekom.sales.data

/**
 * Lightweight quotation model mirroring the `generate-quotation` skill's rules:
 * one line item per SKU, quantity fixed at 1, EUR base with a Switzerland CHF
 * conversion. Prices here are the catalogue's indicative EUR figures — the
 * authoritative quote workbook (PRICES.xlsx) stays the system of record.
 */

data class QuoteLine(
    val sku: String,
    val model: String,
    val eur: Int,
)

data class Quote(
    val company: String,
    val market: String,
    val lines: List<QuoteLine>,
) {
    val totalEur: Int get() = lines.sumOf { it.eur }

    /** EUR→CHF rate used by the skill's worked example. */
    val isSwiss: Boolean get() = market.equals("Switzerland", ignoreCase = true)
    val chfRate: Double = 0.9306
    val totalChf: Double get() = totalEur * chfRate

    companion object {
        fun build(company: String, market: String, skus: List<String>): Quote {
            val lines = skus.mapNotNull { sku ->
                Catalog.bySku(sku)?.let { QuoteLine(sku, it.model, it.indicativeEur) }
            }
            return Quote(company.ifBlank { "<company>" }, market.ifBlank { "Germany" }, lines)
        }
    }
}
