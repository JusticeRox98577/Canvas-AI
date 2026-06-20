# Canvas-AI — native macOS app (App Store edition)

A fully native **SwiftUI** app — no Python, no bundled browser — so it can ship
on the **Mac App Store**. It talks to Canvas with the official REST API using
your **personal access token**, and powers study features with the **Anthropic
API** (your own key). It's study-focused (read, study, draft) — there's no
auto-submit, which is what keeps it App Store-eligible.

## Build it
You need a Mac with **Xcode** and (one-time) **XcodeGen**:

```bash
brew install xcodegen          # one-time
cd macos
xcodegen generate              # creates CanvasAI.xcodeproj from project.yml
open CanvasAI.xcodeproj         # then press Run
```

On first launch, open **Settings** (gear icon) and enter:
- **Canvas URL** — e.g. `https://yourschool.instructure.com`
- **Canvas access token** — Canvas → Account → Settings → **+ New Access Token**
- **Anthropic API key** — from console.anthropic.com (for the study features)

## What's inside
| File | Purpose |
|------|---------|
| `project.yml` | XcodeGen project (sandboxed, hardened runtime, education category) |
| `CanvasAI/CanvasAPI.swift` | Canvas REST client (token auth) |
| `CanvasAI/Anthropic.swift` | Anthropic Messages API client |
| `CanvasAI/AppState.swift` | App settings + state |
| `CanvasAI/ContentView.swift` | UI: Courses sidebar, Study / Modules / Due Dates, Settings |
| `CanvasAI/Assets.xcassets` | App icon set |

## Submitting to the App Store
1. Join the **Apple Developer Program** ($99/yr).
2. In Xcode, set your **Team** and a unique **Bundle Identifier**
   (`project.yml` → `PRODUCT_BUNDLE_IDENTIFIER`, currently `com.canvasai.studyapp`).
3. In **App Store Connect**, create the app record.
4. Xcode → **Product → Archive** → **Distribute App → App Store Connect**.
5. Fill in screenshots, description (see `../SELLING.md`), privacy details, and
   submit for review.

### Honest review notes
- Apple scrutinizes anything that logs into a third-party service. Token-based,
  read/study framing is the safe path — keep the listing about **learning**.
- Don't add auto-submit/auto-quiz to this edition; that's what gets education
  apps rejected or pulled.
- You'll declare data use: the app stores the user's token/key locally and sends
  course text to Anthropic for study features (disclose this in App Privacy).
- Consider moving the token/key to the **Keychain** before launch (currently in
  app storage) for a stronger privacy posture.
