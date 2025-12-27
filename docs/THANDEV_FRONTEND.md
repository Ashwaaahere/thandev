# Thandev Frontend

## Scope

The Thandev frontend is a Next.js 14 application located in `frontend/`. It provides the user interface for all platform features including project management, scan execution, results visualization, security news, and exploit tracking.

## Tech Stack

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS 4**: Utility-first styling
- **Framer Motion**: Animations and transitions
- **NextAuth.js**: Authentication and session management
- **Lucide React**: Icon library

## Routing Structure

Next.js App Router structure (all routes under `app/`):

### Main Routes

- **`/`** (`app/page.tsx`): Landing/home page
- **`/projects`** (`app/projects/page.tsx`): Project list page
- **`/projects/[projectId]`** (`app/projects/[projectId]/page.tsx`): Project detail page
- **`/projects/[projectId]/scans`** (`app/projects/[projectId]/scans/page.tsx`): Scan list for project
- **`/projects/[projectId]/scans/[scanId]`** (`app/projects/[projectId]/scans/[scanId]/page.tsx`): Scan detail page with findings
- **`/exploits`** (`app/exploits/page.tsx`): CVE/exploit feed
- **`/news`** (`app/news/page.tsx`): Security news aggregation
- **`/security`** (`app/security/page.tsx`): Security information page
- **`/dashboard`** (`app/dashboard/page.tsx`): Dashboard (if exists)
- **`/account`** (`app/account/page.tsx`): User account settings
- **`/auth`** (`app/auth/page.tsx`): Authentication pages

### API Routes (Next.js API Routes)

- **`/api/auth/[...nextauth]`**: NextAuth.js authentication endpoints
- **`/api/domains`**: Domain verification endpoints (if exists)

## Core UI Components

### Layout Components

**Location**: `app/layout.tsx`

- Root layout with metadata, theme provider, and global providers
- Includes `ConditionalNavbar` and `ConditionalFooter`
- Wraps all pages with `ThemeProvider` and `Providers` (NextAuth, Toast, ErrorBoundary)

### Navigation

**Location**: `components/ConditionalNavbar.tsx`

- Conditional navbar (shown/hidden based on route)
- User menu with GitHub profile
- Navigation links to projects, exploits, news

### Project Management

**Location**: `app/projects/` and `components/`

- Project list with statistics
- Project creation form
- Project detail view with scan history
- Quick scan button

### Scan Management

**Location**: `app/projects/[projectId]/scans/`

- Scan list with status indicators
- Scan detail page with:
  - Scan metadata (target, level, status, duration)
  - Findings list with filters
  - Finding detail view:
    - "Where it was found" (URL, method, parameter)
    - "What we found" (description)
    - "Why it matters" (impact summary)
    - "How to fix it" (remediation steps)
  - PDF report download buttons (full/executive)
  - Tool execution status

### Findings Display

**Location**: `app/projects/[projectId]/scans/[scanId]/page.tsx`

- Findings list with severity badges
- Filtering by severity, tool, status, category
- Search functionality
- Finding detail modal/section with full information

### Dashboard

**Location**: `app/dashboard/` (if exists)

- Overview statistics
- Recent scans
- Top findings
- Quick actions

## How Frontend Talks to Backend

### API Client

**Location**: `lib/thandevApi.ts`

**Functions:**
- `getAuthHeaders(session)`: Extracts `X-Thandev-User-Id` and `X-Thandev-Tenant-Id` from NextAuth session
- `thandevFetchJSON<T>(url, session, init)`: Authenticated fetch for JSON responses
- `thandevFetchBlob(url, session, init)`: Authenticated fetch for binary responses (PDFs)

**Usage Pattern:**
```typescript
import { thandevFetchJSON } from '@/lib/thandevApi';
import { useSession } from 'next-auth/react';

const { data: session } = useSession();
const projects = await thandevFetchJSON<ProjectListResponse>(
  '/api/projects',
  session
);
```

### Authentication Headers

All API requests include:
- `X-Thandev-User-Id`: User ID from NextAuth session
- `X-Thandev-Tenant-Id`: Tenant ID (currently 1:1 with user ID)

**Future**: Will support org accounts where multiple users share a tenant.

### API Base URL

**Environment Variable**: `NEXT_PUBLIC_API_BASE_URL`

**Default**: `http://localhost:8000` (development)

**Production**: Set to backend URL (e.g., `https://thandev-backend.fly.dev`)

### Error Handling

**API Client**:
- Throws errors for non-ok responses
- Parses FastAPI validation errors (422) into readable messages
- Logs errors to console

**Components**:
- Use try/catch for API calls
- Display error messages to users
- Use toast notifications for success/error feedback

## State Management Patterns

### NextAuth Session

**Location**: `lib/auth.ts` (NextAuth configuration)

**Usage**:
```typescript
import { useSession } from 'next-auth/react';

const { data: session, status } = useSession();
```

**Session Data**:
- `user.id`: User ID (GitHub ID)
- `user.email`: User email
- `user.name`: User name
- `user.image`: User avatar URL

### React Query / SWR

**Status**: Not currently used. Components use direct `fetch` calls with `useEffect` and `useState`.

**Future Consideration**: Could use React Query or SWR for:
- Automatic caching
- Background refetching
- Optimistic updates

### Local State

**Pattern**: `useState` for component-local state

**Example**:
```typescript
const [scans, setScans] = useState<Scan[]>([]);
const [loading, setLoading] = useState(true);

useEffect(() => {
  loadScans();
}, []);
```

### Polling for Scan Status

**Pattern**: `useEffect` with `setInterval` for real-time updates

**Example**:
```typescript
useEffect(() => {
  if (scan.status === 'running' || scan.status === 'queued') {
    const interval = setInterval(() => {
      refreshScan();
    }, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }
}, [scan.status]);
```

## Authentication Flow

### GitHub OAuth

1. **User clicks "Sign in with GitHub"**
2. **NextAuth redirects to GitHub OAuth**
3. **User authorizes on GitHub**
4. **GitHub redirects back with authorization code**
5. **NextAuth exchanges code for access token**
6. **Backend creates/updates user record**
7. **Session created with JWT**
8. **User redirected to dashboard/projects**

### Session Management

- Sessions stored as HTTP-only cookies
- JWT tokens signed with `NEXTAUTH_SECRET`
- Session expires after configured time (default: 30 days)

### Protected Routes

**Pattern**: Check session in page component

```typescript
const { data: session, status } = useSession();

if (status === 'loading') {
  return <Loading />;
}

if (!session) {
  redirect('/auth');
}
```

## Environment Variables

**Location**: `.env.local` (not committed to git)

**Required:**
- `NEXT_PUBLIC_API_BASE_URL`: Backend API URL
- `GITHUB_CLIENT_ID`: GitHub OAuth client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth client secret
- `NEXTAUTH_SECRET`: Secret for JWT signing
- `NEXTAUTH_URL`: Frontend URL (for OAuth callback)

**Optional:**
- `CLOUD_RUN_JOB_URL`: Cloud Run service URL (if using Cloud Run)

## Build and Deployment

### Development

```bash
cd frontend
npm install
npm run dev
```

**Runs on**: `http://localhost:3000`

### Production Build

```bash
npm run build
npm start
```

### Deployment

**Vercel** (recommended):
- Connect GitHub repository
- Set root directory to `frontend`
- Configure environment variables
- Automatic deployments on push to main

**Docker**:
- Dockerfile included in `frontend/`
- Build: `docker build -t thandev-frontend ./frontend`
- Run: `docker run -p 3000:3000 thandev-frontend`

## Styling

### Tailwind CSS

**Configuration**: `tailwind.config.js`

**Theme**: Custom theme with CSS variables for dark/light mode

**Usage**: Utility classes throughout components

### Global Styles

**Location**: `app/globals.css`

- CSS variables for colors (dark/light mode)
- Base styles
- Custom animations

### Component Styling

**Pattern**: Tailwind utility classes + CSS modules (if needed)

**Example**:
```tsx
<div className="bg-surface text-fg p-4 rounded-lg">
  <h2 className="text-xl font-bold">Title</h2>
</div>
```

## TypeScript Types

### Finding Type

**Location**: Defined in scan detail page

```typescript
type Finding = {
  id?: string;
  title: string;
  description?: string | null;
  severity?: string | null;
  status?: FindingStatus;
  url?: string | null;
  http_method?: string | null;
  parameter?: string | null;
  vuln_type?: string | null;
  impact_summary?: string | null;
  remediation_summary?: string | null;
  remediation_steps?: string | null;
  default_remediation_steps?: string | null;
  // ... more fields
};
```

### API Response Types

**Pattern**: Define types matching backend Pydantic schemas

**Example**:
```typescript
type ScanResponse = {
  id: string;
  project_id: string;
  scan_level: 'basic' | 'pro' | 'advanced';
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed';
  summary?: {
    risk_score?: number;
    findings_count?: number;
  };
  // ... more fields
};
```

