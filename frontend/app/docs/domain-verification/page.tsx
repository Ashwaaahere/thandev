import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


export const metadata: Metadata = {
  title: 'Domain Verification | Documentation | Thandev',
  description: 'DNS TXT verification and rules for domain ownership',
};

const mdxContent = `# Domain Verification

Domain verification is a **required security measure** that ensures you only scan domains you own or have explicit permission to test. This prevents unauthorized scanning and abuse.

## Why Domain Verification?

Domain verification protects both you and target owners by:

- **Preventing Unauthorized Scanning**: You can't scan domains you don't own
- **Establishing Ownership**: Proves you control the domain's DNS records
- **Enabling Production Scans**: Required before scanning production targets
- **Reducing Abuse**: Makes it harder for malicious users to scan random targets

## How Domain Verification Works

Domain verification uses **DNS TXT records** to prove domain ownership. When you verify a root domain (e.g., \`example.com\`), you can scan any URL under that domain (e.g., \`https://example.com\`, \`https://app.example.com\`, \`https://example.com/api\`).

### Verification Process

1. **Request Verification**: In your project settings, click "Verify Domain"
2. **Get TXT Record**: Thandev generates a unique TXT record value
3. **Add DNS Record**: Add the TXT record to your domain's DNS settings
4. **Wait for Propagation**: DNS changes can take a few minutes to propagate
5. **Verify**: Thandev checks for the TXT record and marks the domain as verified

## Step-by-Step Verification

### Step 1: Access Domain Verification

1. Navigate to your project
2. Go to "Project Settings" or "Domain Verification"
3. Enter the root domain you want to verify (e.g., \`example.com\`)

### Step 2: Add DNS TXT Record

Thandev will provide a TXT record like:

\`\`\`
Name: @ (or your root domain)
Type: TXT
Value: thandev-verification=abc123xyz789...
TTL: 300 (or default)
\`\`\`

Add this record to your domain's DNS provider (e.g., Cloudflare, AWS Route 53, GoDaddy, etc.).

### Step 3: Wait for DNS Propagation

DNS changes typically propagate within:
- **5-15 minutes** for most providers
- **Up to 48 hours** in rare cases (though usually much faster)

You can check if the record is live using online DNS lookup tools.

### Step 4: Verify Domain

1. Return to Thandev
2. Click "Verify Domain" or "Check Verification"
3. Thandev will query DNS for the TXT record
4. If found, the domain is marked as verified ✅

## Verification Rules

### Root Domain Verification

- Verify the **root domain** (e.g., \`example.com\`)
- Once verified, you can scan **any subdomain** under it:
  - \`https://example.com\`
  - \`https://www.example.com\`
  - \`https://app.example.com\`
  - \`https://api.example.com\`
  - \`https://staging.example.com\`

### Multiple Domains

- Each root domain must be verified separately
- You can verify multiple domains for different projects
- Verified domains are tied to your tenant (account)

### Demo Targets Exception

**Demo targets don't require verification**:

- **bWAPP**: Pre-approved vulnerable web application for learning
- **itsecgames**: Security training applications

These are admin-approved and safe for practice scans.

## Troubleshooting Verification

### TXT Record Not Found

**Problem**: Thandev can't find your TXT record.

**Solutions**:
- Wait a few more minutes (DNS propagation delay)
- Verify the TXT record value is exactly correct (no extra spaces)
- Check that the record is at the root domain (not a subdomain)
- Use a DNS lookup tool to confirm the record is live
- Ensure your DNS provider has saved and published the record

### Verification Expires

**Problem**: Previously verified domain is now unverified.

**Solutions**:
- Check if the TXT record still exists in DNS
- Re-add the TXT record if it was removed
- Re-verify the domain in Thandev

### Wrong Domain Format

**Problem**: Thandev rejects your domain input.

**Solutions**:
- Use the root domain only (e.g., \`example.com\`, not \`https://example.com\`)
- Don't include protocols (http/https) or paths
- Don't include subdomains for root verification

## Best Practices

1. **Verify Early**: Verify domains before creating projects or running scans
2. **Keep Records Active**: Don't delete TXT records after verification (Thandev may re-check)
3. **Use Production DNS**: Add records to your production DNS, not test environments
4. **Document Your Domains**: Keep a list of verified domains for your organization
5. **Test with Demo Targets First**: Practice with bWAPP or itsecgames before production scans

## Security Considerations

- **TXT Record Security**: The verification TXT record is unique to your account but not secret. Anyone can see it via DNS lookup, but they can't use it to verify domains they don't control.
- **Domain Ownership**: Only verify domains you actually own or have permission to scan.
- **Subdomain Scanning**: Be careful when scanning subdomains—ensure you have permission for each subdomain you test.

## Key Points

- Domain verification is **required** for production scans
- Verify the **root domain** to scan all subdomains
- Uses **DNS TXT records** for verification
- DNS propagation typically takes 5-15 minutes
- Demo targets (bWAPP, itsecgames) don't require verification
- Multiple domains can be verified separately
- Keep TXT records active after verification

## FAQ

**Q: Do I need to verify every subdomain?**  
A: No. Verify the root domain (e.g., \`example.com\`) and you can scan all subdomains under it.

**Q: How long does verification take?**  
A: Usually 5-15 minutes after adding the DNS record. Rarely up to 48 hours.

**Q: Can I remove the TXT record after verification?**  
A: Not recommended. Thandev may re-check verification, and removing the record will invalidate verification.

**Q: What if I don't control the domain's DNS?**  
A: You'll need to work with your DNS administrator to add the TXT record, or use demo targets for testing.

**Q: Can I verify domains I don't own?**  
A: No. You can only verify domains where you can add DNS TXT records, which proves ownership or control.

**Q: Do demo targets require verification?**  
A: No. Demo targets like bWAPP and itsecgames are pre-approved by admins and don't require verification.

---

**Last updated**: 2025-12-26`;

export default async function DomainVerificationPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Domain Verification"
      description="DNS TXT verification and rules"
      href="/docs/domain-verification"
      lastUpdated="2025-12-26"
    />
  );
}


