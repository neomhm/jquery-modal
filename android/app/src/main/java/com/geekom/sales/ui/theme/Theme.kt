package com.geekom.sales.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// GEEKOM brand palette
val GeekomOrange = Color(0xFFFF6A00)
val GeekomInk = Color(0xFF0B1220)
val GeekomSlate = Color(0xFF1B2436)
val GeekomMist = Color(0xFFF3F5F8)

private val DarkColors = darkColorScheme(
    primary = GeekomOrange,
    onPrimary = Color.White,
    secondary = Color(0xFFFFB27A),
    background = GeekomInk,
    onBackground = Color(0xFFE6E9EF),
    surface = GeekomSlate,
    onSurface = Color(0xFFE6E9EF),
    surfaceVariant = Color(0xFF232E44),
    onSurfaceVariant = Color(0xFFAEB6C6),
)

private val LightColors = lightColorScheme(
    primary = GeekomOrange,
    onPrimary = Color.White,
    secondary = Color(0xFFB2531A),
    background = GeekomMist,
    onBackground = GeekomInk,
    surface = Color.White,
    onSurface = GeekomInk,
    surfaceVariant = Color(0xFFE7EBF1),
    onSurfaceVariant = Color(0xFF48546B),
)

private val AppTypography = Typography()

@Composable
fun GeekomSalesTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = AppTypography,
        content = content,
    )
}
