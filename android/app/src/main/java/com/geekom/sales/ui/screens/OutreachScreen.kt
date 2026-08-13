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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.geekom.sales.data.Outreach
import com.geekom.sales.data.RenderedEmail
import com.geekom.sales.data.TemplateKind
import com.geekom.sales.ui.ScreenHeader
import com.geekom.sales.ui.shareText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OutreachScreen(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var company by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
    var country by remember { mutableStateOf(Outreach.countries.first()) }
    var kind by remember { mutableStateOf(TemplateKind.MASTER) }
    var countryExpanded by remember { mutableStateOf(false) }
    var email by remember { mutableStateOf<RenderedEmail?>(null) }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState()),
    ) {
        ScreenHeader("Outreach", "Draft a first-contact email from the approved GEEKOM templates.")

        Column(Modifier.padding(horizontal = 20.dp)) {
            OutlinedTextField(
                value = company,
                onValueChange = { company = it; email = null },
                label = { Text("Company") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = contact,
                onValueChange = { contact = it; email = null },
                label = { Text("Contact name (optional)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(10.dp))

            ExposedDropdownMenuBox(
                expanded = countryExpanded,
                onExpandedChange = { countryExpanded = it },
            ) {
                OutlinedTextField(
                    value = "${country.name}  ·  ${country.language}",
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Country / market") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = countryExpanded) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(),
                )
                ExposedDropdownMenu(
                    expanded = countryExpanded,
                    onDismissRequest = { countryExpanded = false },
                ) {
                    Outreach.countries.forEach { c ->
                        DropdownMenuItem(
                            text = { Text("${c.name}  ·  ${c.language}") },
                            onClick = {
                                country = c
                                countryExpanded = false
                                email = null
                            },
                        )
                    }
                }
            }

            Spacer(Modifier.height(14.dp))
            Text("Template", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TemplateKind.entries.forEach { k ->
                    FilterChip(
                        selected = kind == k,
                        onClick = { kind = k; email = null },
                        label = { Text(k.display) },
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { email = Outreach.render(kind, company.ifBlank { "<company>" }, contact, country) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Generate email")
            }

            email?.let { e ->
                Spacer(Modifier.height(18.dp))
                Card(
                    Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Subject", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(e.subject, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(10.dp))
                        Text(e.body, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Render this in ${e.language} before sending — this is the English master. " +
                        "Fill any <angle-bracket> slots and paste the Zoho WorkDrive link.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    onClick = { shareText(context, e.subject, e.body) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Filled.Share, contentDescription = null)
                    Text("  Share / copy")
                }
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}
