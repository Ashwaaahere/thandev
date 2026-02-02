# Privacy Policy & Terms of Service - TODO Items for Founder Review

## Files Updated
- `frontend/app/privacy/page.tsx` - Production-grade Privacy Policy
- `frontend/app/terms/page.tsx` - Production-grade Terms of Service

Both pages are server-rendered (Next.js App Router) and visible in "View Page Source".

---

## TODO Items Requiring Founder Confirmation

### Privacy Policy TODOs

1. **Log Retention Period**
   - Location: Section 3 (Usage and Technical Logs)
   - Action: Add specific retention period (e.g., "Technical logs are retained for 30-90 days")
   - Current: Comment placeholder

2. **Subprocessors List**
   - Location: Section 4 (Information Sharing and Disclosure)
   - Action: Add specific list of subprocessors:
     - Hosting providers (e.g., Azure, Vercel)
     - Database providers (e.g., Supabase)
     - Analytics providers (if used)
     - Email service providers (if used)
   - Current: Placeholder list with TODO comments

3. **Primary Hosting Region**
   - Location: Section 7 (International Users)
   - Action: Specify primary hosting region(s) (e.g., "Our primary infrastructure is hosted in [US East, EU West, etc.]")
   - Current: Generic statement

4. **Child Age Threshold**
   - Location: Section 9 (Children's Privacy)
   - Action: Confirm age threshold (13 or 16 years old)
   - Current: Set to 13 with TODO comment

### Terms of Service TODOs

1. **Governing Law and Jurisdiction**
   - Location: Section 12 (Governing Law and Dispute Resolution)
   - Action: Specify:
     - Governing law jurisdiction (e.g., "laws of New York", "laws of Delaware", "laws of India")
     - Venue for disputes (e.g., "courts of New York, New York", "courts of [City, State/Country]")
   - Current: Generic placeholder

2. **Liability Cap**
   - Location: Section 10 (Limitation of Liability)
   - Action: Confirm liability cap amount or formula
     - Current: "$100 USD or amount paid in 12 months, whichever is greater"
     - May need jurisdiction-specific adjustments

---

## Key Changes Made

### Privacy Policy
✅ Removed device fingerprinting mentions
✅ Removed "stored locally" claims - now accurately states server-side storage
✅ Removed payment information references
✅ Added comprehensive GDPR-style user rights section
✅ Added accurate data collection disclosure
✅ Added data retention and deletion policies
✅ Added security measures disclosure
✅ Added international users section

### Terms of Service
✅ Added comprehensive Authorization/Acceptable Use section (critical for legal protection)
✅ Added Scan Results Disclaimer (protects against false positive/negative claims)
✅ Added Data & Content section (clarifies ownership and server-side storage)
✅ Added Third-Party Tools section (links to tool catalog)
✅ Added Indemnification section
✅ Removed all payment/billing references
✅ Enhanced prohibited activities list
✅ Added beta service disclaimer

---

## Consistency Checks ✅

- ✅ Both pages match on server-side data storage
- ✅ Both pages match on deletion expectations
- ✅ Both pages reference tool usage consistently
- ✅ No leftover mentions of local-only storage
- ✅ No device fingerprinting mentions
- ✅ No payment language
- ✅ Titles and meta descriptions remain unique (SEO)

---

## Next Steps

1. Review all TODO items above
2. Fill in specific values for each TODO
3. Remove TODO comments once values are confirmed
4. Consider legal review if required for your jurisdiction
5. Update "Last updated" dates when making final changes
