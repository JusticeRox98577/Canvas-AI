# Selling Canvas-AI (study-assistant edition)

This is a plan for selling Canvas-AI **as a study and drafting assistant**. Lead
with learning value; the submit/auto-do capability stays an off-by-default
power-user setting and is *not* part of the pitch.

> Before charging money: confirm how you're allowed to access Canvas. Reusing a
> browser-login session via automation may violate Instructure's terms; the
> safest commercial path is the official Canvas API/LTI. Also, "AI that writes
> submittable answers" is banned by many schools — market *understanding and
> studying*, not *producing answers to hand in*.

## Positioning

**One-liner:** "Your AI study partner for Canvas — understand your courses,
quiz yourself, and never miss a due date."

**Who it's for:** college and high-school students who use Canvas and want help
*learning* the material faster.

**What to emphasize (the value):**
- Reads your real course modules, pages, and files — no copy/paste.
- **Study mode:** quiz-me, flashcards, plain-English explanations, summaries —
  all grounded in your actual course material.
- **Due-date dashboard** across every course.
- **Draft assistant** for discussions/assignments that *you* review and post.
- Runs on your own Claude subscription (or local/free model) — your data stays
  with you.

**What NOT to lead with:** auto-submitting graded work or auto-answering quizzes.

## Pricing (suggested)

| Tier | Price | What's included |
|------|-------|-----------------|
| **Free** | $0 | Read modules, due-date dashboard, 10 AI study actions/day |
| **Student** | **$6/mo** or **$39/yr** | Unlimited study mode, drafting, all courses |
| **Lifetime** | **$59 one-time** | Everything, one device, free updates |

Notes:
- Students are price-sensitive — keep it cheap, push the annual/lifetime.
- A free tier drives installs; gate on *volume of AI actions*, not core reading.
- Offer a 7-day full trial so people feel the value before paying.

## How to take payments + licenses

The app already supports online license activation (off by default). To turn it
on for sold builds:

1. Create a product on **LemonSqueezy** (recommended — it's a merchant of
   record, so it handles tax/VAT) or **Gumroad** / **Keygen**.
2. Enable license keys on the product.
3. Build with licensing on:
   ```powershell
   $env:LICENSE_REQUIRED = "true"
   powershell -ExecutionPolicy Bypass -File windows\build.ps1
   ```
4. Buyers get a key by email → enter it on first launch → the app activates and
   validates it online (offline-tolerant after first activation).

To override the license backend, set `LICENSE_ACTIVATE_URL` / `LICENSE_VALIDATE_URL`.

## Distribution

- Ship `Canvas-AI-Setup.exe` (Inno Setup) from your site or the store page.
- Set `UPDATE_URL` to a small JSON (`{"version": "...", "url": "..."}`) so the
  app shows a "new version" banner.
- Consider a **code-signing certificate** (~$100–200/yr) so Windows SmartScreen
  doesn't warn buyers. Optional for a first release.

## A realistic launch checklist

- [ ] Confirm Canvas access method is allowed (API/LTI vs. session reuse).
- [ ] Marketing copy focuses on studying, not submitting.
- [ ] Free trial + clear pricing page.
- [ ] LemonSqueezy product + license keys live.
- [ ] Signed installer + update feed.
- [ ] A simple privacy note (what data is read, where it goes).
- [ ] Support email / FAQ.
