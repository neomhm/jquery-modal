package com.geekom.sales.data

/**
 * GEEKOM mini PC catalogue.
 *
 * The positioning copy (segment, AI-native framing, warranty) mirrors the
 * approved GEEKOM sales collateral. Specs and the indicative EUR price are
 * representative reference data for the sales companion — the authoritative
 * price/spec source remains the internal MODELS.xlsx / PRICES.xlsx workbooks,
 * quoted per SKU through the Quote screen.
 */
data class Product(
    val model: String,
    val tagline: String,
    val segment: Segment,
    val cpu: String,
    val gpu: String,
    val ram: String,
    val storage: String,
    val ports: String,
    val skus: List<String>,
    val indicativeEur: Int,
    val highlights: List<String>,
)

enum class Segment(val label: String) {
    AI("AI-Native"),
    GAMING("Gaming"),
    OFFICE("Office"),
    EDGE("Edge / Signage"),
}

object Catalog {

    val products: List<Product> = listOf(
        Product(
            model = "GEEKOM A8 Max",
            tagline = "Flagship AI-native mini PC",
            segment = Segment.AI,
            cpu = "AMD Ryzen 9 8945HS (8C/16T, up to 5.4 GHz)",
            gpu = "AMD Radeon 780M",
            ram = "Up to 64 GB DDR5",
            storage = "Up to 2 TB PCIe 4.0 NVMe SSD",
            ports = "2× USB4, HDMI 2.0, DisplayPort, 2.5G LAN, Wi-Fi 6E",
            skus = listOf("GMA8MAXR98945HS-321-EU", "GMA8MAXR98945HS-641-EU"),
            indicativeEur = 749,
            highlights = listOf(
                "Ryzen AI NPU for on-device inference",
                "Quad 4K display output",
                "Designed for SMB local AI workloads",
            ),
        ),
        Product(
            model = "GEEKOM A8",
            tagline = "AI performance, mainstream price",
            segment = Segment.AI,
            cpu = "AMD Ryzen 7 8845HS (8C/16T, up to 5.1 GHz)",
            gpu = "AMD Radeon 780M",
            ram = "Up to 32 GB DDR5",
            storage = "Up to 1 TB PCIe 4.0 NVMe SSD",
            ports = "2× USB4, HDMI 2.0, 2.5G LAN, Wi-Fi 6E",
            skus = listOf("GMA8R98845HS-161-EU", "GMA8R98845HS-321-EU"),
            indicativeEur = 579,
            highlights = listOf(
                "Ryzen AI hardware acceleration",
                "Compact 0.6 L chassis",
                "3-year manufacturer warranty",
            ),
        ),
        Product(
            model = "GEEKOM Mini IT13",
            tagline = "Intel Core i9 productivity powerhouse",
            segment = Segment.OFFICE,
            cpu = "Intel Core i9-13900H (14C/20T, up to 5.4 GHz)",
            gpu = "Intel Iris Xe",
            ram = "Up to 32 GB DDR4",
            storage = "Up to 2 TB PCIe 4.0 NVMe SSD",
            ports = "2× USB4, HDMI, DisplayPort, 2.5G LAN, Wi-Fi 6E",
            skus = listOf("GMIT13I913900-322T-EU", "GMIT13I913900-161-EU"),
            indicativeEur = 629,
            highlights = listOf(
                "NUC-class ODM heritage",
                "Quiet dual-fan IceBlade cooling",
                "Ideal for hybrid / home-office fleets",
            ),
        ),
        Product(
            model = "GEEKOM GT13 Pro",
            tagline = "Top-tier gaming & creator mini PC",
            segment = Segment.GAMING,
            cpu = "Intel Core i9-13900HK (14C/20T, up to 5.4 GHz)",
            gpu = "Intel Iris Xe",
            ram = "Up to 64 GB DDR5",
            storage = "Up to 2 TB PCIe 4.0 NVMe SSD",
            ports = "USB4 v2, dual HDMI, 2.5G LAN, Wi-Fi 7",
            skus = listOf("GMGT13PI913900HK-641-EU"),
            indicativeEur = 949,
            highlights = listOf(
                "Wi-Fi 7 connectivity",
                "Dual-channel DDR5 headroom",
                "Creator-grade sustained performance",
            ),
        ),
        Product(
            model = "GEEKOM Air12",
            tagline = "Fanless-quiet everyday desktop",
            segment = Segment.OFFICE,
            cpu = "Intel Core i3-N305 (8C, up to 3.8 GHz)",
            gpu = "Intel UHD Graphics",
            ram = "Up to 16 GB LPDDR5",
            storage = "Up to 1 TB PCIe 3.0 NVMe SSD",
            ports = "USB 3.2, dual HDMI, Gigabit LAN, Wi-Fi 6",
            skus = listOf("GMAIR12N305-081-EU", "GMAIR12N305-161-EU"),
            indicativeEur = 279,
            highlights = listOf(
                "Entry price point for volume tenders",
                "Low power draw",
                "Great thin-client / VDI endpoint",
            ),
        ),
        Product(
            model = "GEEKOM XT13 Pro",
            tagline = "Edge & digital-signage workhorse",
            segment = Segment.EDGE,
            cpu = "Intel Core i9-13900H (14C/20T, up to 5.4 GHz)",
            gpu = "Intel Iris Xe",
            ram = "Up to 32 GB DDR5",
            storage = "Up to 2 TB PCIe 4.0 NVMe SSD",
            ports = "2× USB4, dual HDMI, 2.5G LAN, Wi-Fi 6E",
            skus = listOf("GMXT13PI913900-321-EU"),
            indicativeEur = 699,
            highlights = listOf(
                "24/7 interactive-terminal ready",
                "Quad 8K display support",
                "VESA mount included",
            ),
        ),
    )

    fun bySku(sku: String): Product? =
        products.firstOrNull { p -> p.skus.any { it.equals(sku, ignoreCase = true) } }

    val allSkus: List<String>
        get() = products.flatMap { it.skus }
}
