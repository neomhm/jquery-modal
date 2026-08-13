package com.geekom.sales.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.geekom.sales.data.Catalog
import com.geekom.sales.data.Outreach
import com.geekom.sales.data.Quote
import com.geekom.sales.ui.ScreenHeader
import com.geekom.sales.ui.shareText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuoteScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var company by remember { mutableStateOf("") }
    var market by remember { mutableStateOf("Germany") }
    var marketExpanded by remember { mutableStateOf(false) }
    val chosen = remember { mutableStateListOf<String>() }
    var quote by remember { mutableStateOf<Quote?>(null) }

    val markets = Outreach.countries.map { it.name }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        ScreenHeader("Quote", "Build a by-SKU offer. One line per SKU, quantity 1.")

        Column(Modifier.padding(horizontal = 20.dp)) {
            OutlinedTextField(
                value = company,
                onValueChange = { company = it; quote = null },
                label = { Text("Company") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(10.dp))

            ExposedDropdownMenuBox(expanded = marketExpanded, onExpandedChange = { marketExpanded = it }) {
                OutlinedTextField(
                    value = market,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Market") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = marketExpanded) },
                    modifier = Modifier.fillMaxWidth().menuAnchor(),
                )
                ExposedDropdownMenu(expanded = marketExpanded, onDismissRequest = { marketExpanded = false }) {
                    markets.forEach { m ->
                        DropdownMenuItem(
                            text = { Text(m) },
                            onClick = { market = m; marketExpanded = false; quote = null },
                        )
                    }
                }
            }

            Spacer(Modifier.height(14.dp))
            Text("Select SKUs", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            Catalog.products.forEach { product ->
                Text(
                    product.model,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Column {
                    product.skus.forEach { sku ->
                        val selected = sku in chosen
                        FilterChip(
                            selected = selected,
                            onClick = {
                                if (selected) chosen.remove(sku) else chosen.add(sku)
                                quote = null
                            },
                            label = { Text(sku, fontFamily = FontFamily.Monospace) },
                            modifier = Modifier.padding(vertical = 2.dp),
                        )
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { quote = Quote.build(company, market, chosen.toList()) },
                enabled = chosen.isNotEmpty(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Build quote")
            }

            quote?.let { q -> QuoteResult(q, onShare = { shareText(context, "GEEKOM quote — ${q.company}", quoteAsText(q)) }) }
            Spacer(Modifier.height(28.dp))
        }
    }
}

@Composable
private fun QuoteResult(q: Quote, onShare: () -> Unit) {
    Spacer(Modifier.height(18.dp))
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(q.company, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("Market: ${q.market}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(12.dp))
            q.lines.forEach { line ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.padding(end = 8.dp)) {
                        Text(line.model, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        Text(line.sku, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text("€${line.eur}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(6.dp))
                Divider()
                Spacer(Modifier.height(6.dp))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Total", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("€${q.totalEur}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
            if (q.isSwiss) {
                Text(
                    "≈ CHF %.2f  (EUR→CHF %.4f)".format(q.totalChf, q.chfRate),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
    Spacer(Modifier.height(8.dp))
    Text(
        "Indicative EUR from the catalogue. Confirm against PRICES.xlsx before issuing.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(10.dp))
    OutlinedButton(onClick = onShare, modifier = Modifier.fillMaxWidth()) {
        Icon(Icons.Filled.Share, contentDescription = null)
        Text("  Share quote")
    }
}

private fun quoteAsText(q: Quote): String = buildString {
    appendLine("GEEKOM — Indicative quotation")
    appendLine("Customer: ${q.company}")
    appendLine("Market:   ${q.market}")
    appendLine()
    q.lines.forEach { appendLine("- ${it.model}  [${it.sku}]  €${it.eur}") }
    appendLine()
    appendLine("Total: €${q.totalEur}")
    if (q.isSwiss) appendLine("       ≈ CHF %.2f (EUR->CHF %.4f)".format(q.totalChf, q.chfRate))
    appendLine()
    appendLine("Every line item is quantity 1. Indicative EUR pricing — confirm before issuing.")
}
