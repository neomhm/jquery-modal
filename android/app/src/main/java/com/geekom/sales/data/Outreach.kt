package com.geekom.sales.data

/**
 * Outreach engine — ports the GEEKOM `outreach` skill's country→language map
 * and the two approved email templates into the app.
 *
 * The templates carry approved GEEKOM copy (the 40M€ 2026 figure, the ASUS /
 * TECNO / Intel ODM relationships, the 3-year warranty, the German central
 * warehouse). They are rendered, never rewritten. Any slot that cannot be
 * filled is left visible in <angle brackets> so the sender completes it.
 */

data class Country(
    val name: String,
    val language: String,
    /** Adjective form used for "100% X-speaking support". */
    val languageAdjective: String,
    /** National EPR/WEEE scheme, or the generic European wording when unsure. */
    val eprScheme: String,
)

enum class TemplateKind(val display: String) {
    MASTER("Listing conversation"),
    MEETING_ALAN("Meeting with Alan (CEO)"),
}

object Outreach {

    /** Country list from the skill's language table, with EPR schemes. */
    val countries: List<Country> = listOf(
        Country("France", "French", "French", "the French EPR/WEEE scheme (Ecologic / ecosystem)"),
        Country("Germany", "German", "German", "the German ElektroG / stiftung ear scheme"),
        Country("Austria", "German", "German", "the Austrian EAG-VO / EAK scheme"),
        Country("Switzerland", "German", "German", "the Swiss SENS / SWICO scheme"),
        Country("Belgium", "Dutch", "Dutch", "the Belgian Recupel scheme"),
        Country("Netherlands", "Dutch", "Dutch", "the Dutch WEEE (OPEN / Stichting) scheme"),
        Country("Italy", "Italian", "Italian", "the Italian RAEE scheme"),
        Country("Spain", "Spanish", "Spanish", "the Spanish RAEE scheme"),
        Country("Portugal", "Portuguese", "Portuguese", "the Portuguese REEE scheme"),
        Country("Poland", "Polish", "Polish", "the Polish ZSEE scheme"),
        Country("United Kingdom", "English", "English", "the UK WEEE regulations"),
        Country("Ireland", "English", "English", "the Irish WEEE (WEEE Ireland) scheme"),
        Country("Sweden", "English", "English", "the generic European WEEE/EPR requirements"),
        Country("Denmark", "English", "English", "the generic European WEEE/EPR requirements"),
        Country("Norway", "English", "English", "the generic European WEEE/EPR requirements"),
        Country("Finland", "English", "English", "the generic European WEEE/EPR requirements"),
    )

    fun countryByName(name: String): Country? =
        countries.firstOrNull { it.name.equals(name, ignoreCase = true) }

    /**
     * The IFA sentence is valid only until IFA Berlin, September 2026.
     * Kept as a flag so it can be dropped once the show has passed.
     */
    const val ifaWindowOpen: Boolean = true

    fun render(kind: TemplateKind, company: String, contactName: String, country: Country): RenderedEmail {
        val name = contactName.ifBlank { "<contact name>" }
        return when (kind) {
            TemplateKind.MASTER -> master(company, name, country)
            TemplateKind.MEETING_ALAN -> meetingAlan(company, name, country)
        }
    }

    private fun master(company: String, name: String, c: Country): RenderedEmail {
        val ifaLine = if (ifaWindowOpen)
            " Please also note that we will be present at the IFA in Berlin in September, " +
                "which could provide an excellent opportunity for a meeting." else ""
        val subject = "GEEKOM × $company — mini PC distribution partnership"
        val body = """
            Dear $name,

            I represent GEEKOM, a leading global player in the mini PC market (AI, Gaming, Office) and a historic ODM partner of ASUS, TECNO, and Intel for the NUC series.

            We would like to evaluate a distribution partnership with $company to list our portfolio and establish it within your distribution network.

            The GEEKOM brand, which was launched in Europe just a year ago, is experiencing exceptional acceptance, with revenue already exceeding 40 million euros in 2026. This momentum positions us among the fastest-growing IT manufacturers in the European market.

            Our "AI-Native" mini PCs offer unrivaled performance in this segment and have been specifically designed to democratize hardware acceleration and local AI processing for small and medium-sized enterprises (SMEs).

            In this context, we are convinced that $company is the ideal partner to market this new category of "AI PCs" in the ${c.name} market.

            I would be delighted to explore all collaboration possibilities with you, whether by phone, via email, or in person.$ifaLine

            Below you will find our secure folder containing the complete product range, detailed data sheets, and the company presentation:
            🔗 Distributors - Zoho WorkDrive <URL>

            Key benefits of a GEEKOM partnership:

            - Pioneers in AI and Performance: Latest-generation Intel and AMD architectures, optimized for gaming, demanding production workloads, and the acceleration of AI processes.
            - Coverage of All Segments: From hybrid environments (home office) and edge computing to digital signage (24/7 interactive terminals) and thin clients (VDI, POS, industry).
            - Seamless European Logistics: Central warehouse in Germany, guaranteeing extremely fast deliveries and restocking to ${c.name}.
            - Reliability and Full Compliance: 3-year manufacturer's warranty, CE/FCC/RoHS certifications, and compliance with European VAT directives as well as ${c.eprScheme}.
            - Local Support: A 100% ${c.languageAdjective}-speaking customer service team for transparent and reliable returns processing.
            - Proven Market Traction: Very high demand that has already been confirmed by leading European distributors and retailers.

            I remain at your disposal for any further information.

            Best regards,

            Laurent Chammas
            GEEKOM
        """.trimIndent()
        return RenderedEmail(subject, body, c.language)
    }

    private fun meetingAlan(company: String, name: String, c: Country): RenderedEmail {
        val subject = "GEEKOM × $company — meeting with our CEO, second half of September"
        val body = """
            Dear $name,

            I represent GEEKOM, a leading player in the global mini PC market (AI, Gaming, Office) and a long-standing ODM partner of ASUS, TECNO and Intel for the NUC series.

            Alan Chen, CEO of GEEKOM, will be at IFA in Berlin this September and is touring Europe afterwards to meet the distributors we would most like to work with. We would like to include $company in that itinerary. Any day in the second half of September works for us, and we will fit around your calendar.

            Our "AI-Native" mini PCs deliver unrivalled performance in this segment and are designed specifically to make hardware acceleration and local AI processing accessible to small and medium-sized businesses.

            We are convinced that $company is the ideal partner to bring this new "AI PC" category to market in ${c.name}.

            The brand launched in Europe just a year ago and our revenue already exceeds 40 million euros in 2026, which places us among the fastest-growing IT manufacturers on the European market.

            If it is useful ahead of the meeting, our secure folder holds the full range, detailed data sheets and the company presentation:
            🔗 Distributors - Zoho WorkDrive <URL>

            Let me know which day in the second half of September suits you and I will confirm straight away.

            Kind regards,

            Laurent Chammas
            GEEKOM
        """.trimIndent()
        return RenderedEmail(subject, body, c.language)
    }
}

data class RenderedEmail(
    val subject: String,
    val body: String,
    /** Language the email should ultimately be written in (English master here). */
    val language: String,
) {
    val asPlainText: String get() = "Subject: $subject\n\n$body"
}
