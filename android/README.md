# GEEKOM Sales — Android app

A native **Kotlin + Jetpack Compose** companion app for the GEEKOM mini PC B2B
sales workflow. It packages the two things the "geek" sales toolkit does — the
**outreach** email templates and the **quotation** builder — plus a browsable
product **catalog**, into a phone app for the field.

## Screens

| Tab | What it does |
|-----|--------------|
| **Catalog** | Browse the GEEKOM range (AI / Gaming / Office / Edge), tap a model for full specs, highlights and SKUs. |
| **Outreach** | Enter a company + contact, pick a country and a template (*listing* or *Meeting Alan*), and generate a ready-to-fill email. Country drives the support language and the EPR/WEEE scheme, exactly like the `outreach` skill. Share it straight to Gmail/Outlook. |
| **Quote** | Pick SKUs, choose the market, and build a by-SKU offer (one line per SKU, quantity 1, EUR with a Switzerland CHF conversion) — mirroring the `generate-quotation` rules. Share as plain text. |
| **About** | The approved GEEKOM positioning facts. |

## Approved copy vs. reference data

- **Verbatim (approved):** both email templates, and every brand claim — the
  €40M 2026 revenue, the ASUS / TECNO / Intel ODM heritage, the 3-year warranty,
  the German central warehouse.
- **Indicative reference data:** product specs and the catalogue EUR prices. The
  authoritative source stays the internal `MODELS.xlsx` / `PRICES.xlsx`
  workbooks; drop those in behind the `Catalog` / `Quote.build` data layer to
  make pricing authoritative.

## Build & run

Requires Android Studio (Koala or newer) or a local Android SDK.

```bash
# From this android/ directory, first generate the Gradle wrapper once
# (needs a local Gradle, or just open the folder in Android Studio which does it for you):
gradle wrapper --gradle-version 8.7

# then:
./gradlew assembleDebug        # build the APK
./gradlew installDebug         # install on a connected device/emulator
```

Or simply **open the `android/` folder in Android Studio** and press Run — it
provisions the wrapper, SDK and an emulator automatically.

- **Package:** `com.geekom.sales`
- **minSdk:** 26 · **targetSdk / compileSdk:** 34
- **Language:** Kotlin · **UI:** Jetpack Compose (Material 3)

## Project layout

```
android/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/geekom/sales/
│       │   ├── MainActivity.kt            # bottom-nav shell
│       │   ├── data/                      # Products, Outreach, Quote engines
│       │   └── ui/                        # theme, components, screens
│       └── res/                           # brand theme, adaptive launcher icon
├── build.gradle.kts
└── settings.gradle.kts
```
