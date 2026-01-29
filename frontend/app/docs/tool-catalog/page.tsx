import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


export const metadata: Metadata = {
  title: 'Tool Catalog | Documentation | Thandev',
  description: 'All security tools covered and their limits',
};

const mdxContent = `# Tool Catalog

This page provides information about the security tools used in Thandev scans.

## Overview

Thandev uses industry-standard security testing tools to perform comprehensive security assessments. Tool configurations and capabilities are continuously updated to provide the best security coverage.

## Scan Levels

Thandev offers different scan levels with varying tool coverage:

- **Basic Scans**: Essential security testing
- **Pro Scans**: Enhanced security testing with additional tools
- **Advanced Scans**: Comprehensive security testing with full tool suite

## Tool Information

For detailed information about specific tools used in scans, please refer to your scan reports or contact support.

---

**Last updated**: 2025-12-26`;

export default async function ToolCatalogPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Tool Catalog"
      description="All security tools covered and their limits"
      href="/docs/tool-catalog"
      lastUpdated="2025-12-26"
    />
  );
}


