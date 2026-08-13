package com.geekom.sales

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Mail
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Widgets
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Widgets
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import com.geekom.sales.ui.screens.AboutScreen
import com.geekom.sales.ui.screens.CatalogScreen
import com.geekom.sales.ui.screens.OutreachScreen
import com.geekom.sales.ui.screens.QuoteScreen
import com.geekom.sales.ui.theme.GeekomSalesTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            GeekomSalesTheme {
                Surface {
                    GeekomApp()
                }
            }
        }
    }
}

private enum class Tab(
    val label: String,
    val filled: ImageVector,
    val outlined: ImageVector,
) {
    CATALOG("Catalog", Icons.Filled.Widgets, Icons.Outlined.Widgets),
    OUTREACH("Outreach", Icons.Filled.Mail, Icons.Outlined.Mail),
    QUOTE("Quote", Icons.Filled.ReceiptLong, Icons.Outlined.ReceiptLong),
    ABOUT("About", Icons.Filled.Info, Icons.Outlined.Info),
}

@Composable
private fun GeekomApp() {
    var current by remember { mutableStateOf(Tab.CATALOG) }

    Scaffold(
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { tab ->
                    val selected = tab == current
                    NavigationBarItem(
                        selected = selected,
                        onClick = { current = tab },
                        icon = {
                            Icon(
                                imageVector = if (selected) tab.filled else tab.outlined,
                                contentDescription = tab.label,
                            )
                        },
                        label = { Text(tab.label) },
                    )
                }
            }
        },
    ) { padding ->
        val contentModifier = Modifier.padding(padding)
        when (current) {
            Tab.CATALOG -> CatalogScreen(contentModifier)
            Tab.OUTREACH -> OutreachScreen(contentModifier)
            Tab.QUOTE -> QuoteScreen(contentModifier)
            Tab.ABOUT -> AboutScreen(contentModifier)
        }
    }
}
