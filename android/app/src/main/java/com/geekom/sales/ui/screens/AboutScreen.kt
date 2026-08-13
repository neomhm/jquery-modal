package com.geekom.sales.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.geekom.sales.ui.ScreenHeader

@Composable
fun AboutScreen(modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        ScreenHeader("About", "GEEKOM mini PC distribution — sales companion.")
        Column(Modifier.padding(horizontal = 20.dp)) {
            Fact("Positioning", "Leading global player in the mini PC market (AI, Gaming, Office); historic ODM partner of ASUS, TECNO and Intel for the NUC series.")
            Fact("Traction", "Launched in Europe a year ago; 2026 revenue already exceeding €40 million — among the fastest-growing IT manufacturers in Europe.")
            Fact("Logistics", "Central warehouse in Germany for fast delivery and restocking across the European market.")
            Fact("Assurance", "3-year manufacturer warranty; CE / FCC / RoHS certified; European VAT and national EPR/WEEE compliance.")
            Fact("This app", "A companion for the GEEKOM B2B sales workflow: browse the range, draft approved outreach emails, and build by-SKU quotes. Approved copy is carried verbatim; prices/specs shown are indicative reference data.")
            Spacer(Modifier.height(24.dp))
            Text(
                "GEEKOM Sales · v1.0",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun Fact(title: String, body: String) {
    Card(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(4.dp))
            Text(body, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
