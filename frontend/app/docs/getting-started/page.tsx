import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Getting Started | Documentation | Thandev',
  description: 'Account approval and first scan flow guide',
  alternates: {
    canonical: `${SITE_URL}/docs/getting-started`,
  },
};

const mdxContent = `# Getting Started

Welcome to Thandev! This guide will walk you through the process of getting your account approved and running your first security scan.

## Account Approval Process

Thandev uses a **manual approval system** for new accounts. Here's what to expect:

### Step 1: Sign Up with GitHub

1. Navigate to the Thandev homepage
2. Click "Sign in with GitHub"
3. Authorize Thandev to access your GitHub account
4. You'll be redirected back to Thandev

### Step 2: Wait for Admin Approval

After signing up, your account will be in a **pending** state. An administrator must manually approve your account before you can:

- Create projects
- Run security scans
- Access scan results

**Note**: Admin approval typically happens within 1-2 business days. You'll receive an email notification when your account is approved.

### Step 3: Account Approval

Once an admin approves your account:

- Your account status changes to **approved**
- You'll be assigned a plan (Basic, Pro, or Enterprise)
- You can now create projects and run scans

**Note**: You cannot self-select your plan. Plans are assigned by administrators based on your needs and usage.

## Before Your First Scan

Before running a scan on a production target, you must complete domain verification. See the [Domain Verification](/docs/domain-verification) guide for detailed steps.

For testing purposes, you can use admin-approved demo targets like:
- **bWAPP**: A deliberately vulnerable web application for learning
- **itsecgames**: Security training applications

These targets don't require domain verification and are safe for practice.

## Running Your First Scan

### Step 1: Create a Project

1. Navigate to the **Projects** page
2. Click "Create New Project"
3. Enter:
   - **Project Name**: A descriptive name (e.g., "My Web App")
   - **Target URL**: The URL you want to scan
   - **Description** (optional): Additional context
4. Click "Create Project"

### Step 2: Verify Domain Ownership (Production Only)

If scanning a production target:

1. Go to your project settings
2. Follow the DNS TXT record verification steps
3. Wait for verification to complete (usually within minutes)

**Important**: You can only scan URLs under domains you've verified.

### Step 3: Start a Scan

1. Open your project
2. Click "Start New Scan"
3. Select a scan level:
   - **Basic**: Fast, essential coverage (3-8 minutes)
   - **Pro**: Comprehensive coverage (10-25 minutes)
   - **Advanced**: Complete coverage including SQL injection (20-45 minutes)
4. Click "Start Scan"

### Step 4: Monitor Progress

- The scan status will update in real-time (polling every few seconds)
- You'll see progress for each tool execution
- When complete, you'll be notified and can view results

### Step 5: Review Findings

1. Navigate to the scan results page
2. Review findings organized by severity (Critical, High, Medium, Low, Info)
3. Click on individual findings for details
4. Export reports as needed (Executive or Full PDF)

## What Happens During a Scan?

1. **Scan Planning**: The Brain Service (if available) analyzes your target and creates an intelligent scan plan
2. **Tool Execution**: Each security tool runs in sequence based on the plan
3. **Finding Ingestion**: Tool outputs are parsed and findings are stored in the database
4. **Deduplication**: Duplicate findings are identified and merged
5. **Completion**: Scan status updates to "completed" and results are available

**Note**: If the Brain Service is unavailable, scans use default tool configurations.

## Key Points

- Account approval is required and done manually by administrators
- Plans are assigned by admins (no self-selection)
- Domain verification is required for production scans
- Demo targets (bWAPP, itsecgames) are available for practice
- Three scan levels offer different coverage and duration
- Scan progress updates via polling (not WebSocket)
- Results are available immediately after scan completion

## FAQ

**Q: How long does account approval take?**  
A: Typically 1-2 business days. You'll receive an email when approved.

**Q: Can I choose my plan?**  
A: No. Plans are assigned by administrators based on your needs.

**Q: Do I need to verify domains for demo targets?**  
A: No. Demo targets like bWAPP and itsecgames are pre-approved and don't require verification.

**Q: What if my scan fails?**  
A: Check the scan logs for error messages. Common issues include network connectivity, target unavailability, or invalid URLs.

**Q: Can I cancel a running scan?**  
A: Currently, scans cannot be cancelled once started. Wait for completion or contact support.

**Q: How do I know when my scan is done?**  
A: The scan status will update to "completed" and you'll see a notification. You can also refresh the page to check status.

---

**Last updated**: 2025-12-26`;

export default async function GettingStartedPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Getting Started"
      description="Account approval and first scan flow"
      href="/docs/getting-started"
      lastUpdated="2025-12-26"
    />
  );
}


