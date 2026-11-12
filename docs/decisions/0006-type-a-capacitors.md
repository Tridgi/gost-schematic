# ADR-0006 — External Type A font and independent capacitor templates

Status: implemented experimentally; requires visual approval.

1. ГОСТ font specifications are physical metrics, not CSS font-size.
   Capital-height calibration is enforced via actual FreeType glyphs.
2. Font binaries are separate from source, installed under their own
   OFL license or supplied by the document owner with appropriate rights.
3. Font substitution is not accepted as ГОСТ verification. Output
   explicitly records the family and computes collision bounds against
   the actual local file; portable outline/embedding exports are future work.
4. Fixed and polarized capacitor variants are two explicit versioned
   symbols, not dynamically modified resistor objects.
5. Polarized marker and bodies are drafts pending comparison with KOMPAS.
   Physical pins and text collision zones still use the same reusable
   interfaces already approved in architecture stages 0.5–0.7.

Verification: new font profile, installer, geometry and nominal tests.
CI attempts a real OpenGOST Type A sample; failure must be repaired,
not hidden by silently substituting a generic font.
