# Thandev Security Model

## Multi-Tenancy Model

### Isolation Strategy

**Model**: Row-level security via foreign keys

**Implementation**:
- All data models include `tenant_id` and/or `owner_id` foreign keys
- All database queries filter by tenant/user context
- No cross-tenant data access possible

**Key Models**:
- **Project**: `tenant_id`, `owner_id` (user who created project)
- **ScanJob**: `project_id` → `Project.tenant_id`, `Project.owner_id`
- **Finding**: `scan_job_id` → `ScanJob.project_id` → `Project.tenant_id`
- **User**: Belongs to a `Tenant` (currently 1:1, future: many-to-one)

### Tenant Context

**Source**: HTTP headers
- `X-Thandev-Tenant-Id`: Tenant ID
- `X-Thandev-User-Id`: User ID

**Extraction**: `backend/app/core/tenant_utils.py`
- `require_tenant()`: FastAPI dependency that extracts tenant from headers
- `get_current_user()`: FastAPI dependency that extracts user from headers

**Usage Pattern**:
```python
@router.get("/projects")
async def list_projects(
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    # All queries automatically filter by tenant and user
    projects = db.query(Project).filter(
        Project.tenant_id == tenant.id,
        Project.owner_id == current_user.id
    ).all()
```

### Tenant-User Relationship

**Current**: 1:1 mapping (each user has their own tenant)

**Future**: Many-to-one (multiple users can belong to one organization/tenant)

**Implementation**:
- `User` model has `tenant_id` foreign key
- Frontend currently sets `X-Thandev-Tenant-Id` = `X-Thandev-User-Id`
- Backend accepts both headers for flexibility

## Authentication

### GitHub OAuth

**Provider**: GitHub OAuth 2.0

**Flow**:
1. User clicks "Sign in with GitHub"
2. Frontend redirects to GitHub OAuth authorization URL
3. User authorizes on GitHub
4. GitHub redirects back with authorization code
5. NextAuth.js exchanges code for access token
6. Backend creates/updates `User` record with GitHub ID
7. Session created with JWT

**Configuration**:
- **Frontend**: NextAuth.js (`lib/auth.ts`)
- **Backend**: Validates user via `get_current_user()` dependency
- **Session**: HTTP-only cookies, JWT signed with `NEXTAUTH_SECRET`

### Session Management

**Storage**: HTTP-only cookies (secure, httpOnly)

**Token**: JWT (JSON Web Token)

**Expiration**: Configurable (default: 30 days)

**Secret**: `NEXTAUTH_SECRET` environment variable (must be strong in production)

### User Model

**Location**: `backend/app/models/user.py`

**Fields**:
- `id`: UUID primary key
- `email`: User email (from GitHub)
- `name`: User name (from GitHub)
- `github_id`: GitHub user ID (unique identifier)
- `tenant_id`: Foreign key to `Tenant`

**Creation**: Automatic on first OAuth login

**Update**: Email/name updated on each login (if changed on GitHub)

## Authorization

### Role-Based Access Control

**Current Status**: No explicit roles/permissions system

**Access Control**:
- Users can only access their own projects
- All API endpoints require tenant/user context
- No admin or superuser roles

**Future Considerations**:
- Organization roles (admin, member, viewer)
- Project-level permissions
- API key-based authentication for programmatic access

### API Endpoint Protection

**Pattern**: All endpoints use dependencies:
```python
@router.get("/projects")
async def list_projects(
    tenant: Tenant = Depends(require_tenant),
    current_user: User = Depends(get_current_user),
):
    # Endpoint logic
```

**Enforcement**:
- `require_tenant()`: Raises HTTP 401 if tenant header missing
- `get_current_user()`: Raises HTTP 401 if user header missing or invalid
- All queries filter by tenant/user automatically

## Data Protection

### Secrets Management

**Storage**: Environment variables

**Secrets Stored**:
- `DATABASE_URL`: Database connection string (may contain password)
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key
- `GITHUB_CLIENT_SECRET`: GitHub OAuth secret
- `NEXTAUTH_SECRET`: JWT signing secret
- `SECRET_KEY`: Backend JWT secret

**Best Practices**:
- Never commit secrets to version control
- Use `.env` files for local development (gitignored)
- Use platform secrets management (Fly.io secrets, Vercel environment variables)
- Rotate secrets regularly

### Encryption

**In Transit**:
- HTTPS/TLS for all HTTP communication
- Frontend → Backend: HTTPS in production
- Backend → Brain Service: HTTP in development, HTTPS in production (if deployed separately)
- Database connections: SSL/TLS (if configured)

**At Rest**:
- Database: Relies on database encryption (PostgreSQL encryption at rest)
- Files: No explicit file encryption (tool outputs stored as plain text)
- Secrets: Stored as environment variables (platform-dependent encryption)

### Input Validation

**Backend**:
- Pydantic models validate all API request/response data
- SQLAlchemy ORM prevents SQL injection
- URL validation for target URLs
- Type checking and coercion

**Frontend**:
- TypeScript type checking
- Form validation
- React's built-in XSS protection (automatic escaping)

### SQL Injection Prevention

**Method**: SQLAlchemy ORM

**Pattern**: Parameterized queries only

**Example**:
```python
# Safe: ORM query
projects = db.query(Project).filter(Project.tenant_id == tenant.id).all()

# Never: Raw SQL with string formatting
# projects = db.execute(f"SELECT * FROM projects WHERE tenant_id = '{tenant.id}'")
```

### XSS Prevention

**Frontend**:
- React automatically escapes content in JSX
- No `dangerouslySetInnerHTML` usage (unless explicitly needed and sanitized)
- Content Security Policy (CSP) headers

**Backend**:
- JSON responses (no HTML rendering)
- Proper content-type headers

### CORS Protection

**Configuration**: `CORS_ORIGINS` environment variable

**Default**: `http://localhost:3000,http://127.0.0.1:3000,https://thandev.com`

**Implementation**: FastAPI `CORSMiddleware`

**Production**: Restrict to production frontend domain only

### Rate Limiting

**Backend**:
- SlowAPI middleware for rate limiting
- Endpoint-specific limits:
  - Exploits: 100 requests/minute
  - Exploit Stats: 30 requests/minute
  - Security Scans: 10 requests/minute
  - Performance Scans: 10 requests/minute

**Frontend**:
- No explicit rate limiting (relies on backend)

## Security Headers

**Backend**:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (if configured)
- `Content-Security-Policy` (if configured)

**Frontend**:
- Next.js sets security headers automatically
- CSP configured in `next.config.mjs`

## Audit Logging

**Model**: `AuditLog` (if implemented)

**Location**: `backend/app/models/audit_log.py`

**Purpose**: Track user actions for security auditing

**Status**: Model exists but may not be fully integrated

**Future**: Log all sensitive operations (scan creation, finding status changes, etc.)

## Vulnerability Disclosure

**Process**: Not explicitly defined in codebase

**Recommendation**: Implement responsible disclosure process:
1. Security issues reported to security@thandev.com (or similar)
2. Acknowledgment within 48 hours
3. Fix timeline communicated
4. Public disclosure after fix (coordinated disclosure)

## Compliance Considerations

**Current Status**: No explicit compliance certifications

**Future Considerations**:
- SOC 2 Type II
- GDPR compliance (if serving EU users)
- Data retention policies
- Right to deletion (GDPR Article 17)

## Security Best Practices

### For Developers

1. **Never commit secrets**: Use `.env` files (gitignored)
2. **Validate all inputs**: Use Pydantic models
3. **Use parameterized queries**: Never string formatting in SQL
4. **Keep dependencies updated**: Regular security updates
5. **Review code changes**: Security-sensitive changes require review

### For Operators

1. **Rotate secrets regularly**: Especially `NEXTAUTH_SECRET` and `SECRET_KEY`
2. **Monitor logs**: Watch for suspicious activity
3. **Keep services updated**: Regular security patches
4. **Use strong secrets**: Long, random, unique secrets
5. **Enable HTTPS**: Always in production

### For Users

1. **Use strong GitHub passwords**: First line of defense
2. **Review scan results**: Understand findings before acting
3. **Report security issues**: Responsible disclosure
4. **Keep projects private**: Don't share sensitive target URLs publicly

