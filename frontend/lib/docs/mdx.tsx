'use client';

import { MDXRemote, MDXRemoteSerializeResult } from 'next-mdx-remote';
import Link from 'next/link';

export const mdxComponents = {
  a: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    if (href?.startsWith('/docs/')) {
      return (
        <Link href={href} style={{ color: 'var(--brand)' }} className="hover:underline" {...props}>
          {children}
        </Link>
      );
    }
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--brand)' }} className="hover:underline" {...props}>
        {children}
      </a>
    );
  },
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="text-3xl font-bold mt-8 mb-4" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="text-2xl font-bold mt-6 mb-3" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="text-xl font-semibold mt-4 mb-2" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-4 leading-relaxed" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc list-inside mb-4 space-y-2 ml-4" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: React.HTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal list-inside mb-4 space-y-2 ml-4" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="mb-1" style={{ color: 'var(--fg)' }} {...props}>
      {children}
    </li>
  ),
  code: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
    <code
      className="px-1.5 py-0.5 rounded text-sm font-mono"
      style={{
        background: 'var(--surface)',
        color: 'var(--brand)',
        border: '1px solid var(--border)',
      }}
      {...props}
    >
      {children}
    </code>
  ),
  pre: ({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) => (
    <pre
      className="p-4 rounded-lg mb-4 overflow-x-auto"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
      }}
      {...props}
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...props }: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote
      className="border-l-4 pl-4 my-4 italic"
      style={{
        borderColor: 'var(--brand)',
        color: 'var(--muted)',
      }}
      {...props}
    >
      {children}
    </blockquote>
  ),
  hr: ({ ...props }: React.HTMLAttributes<HTMLHRElement>) => (
    <hr className="my-8" style={{ borderColor: 'var(--border)' }} {...props} />
  ),
  table: ({ children, ...props }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto mb-4">
      <table className="min-w-full border-collapse" style={{ borderColor: 'var(--border)' }} {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <th
      className="px-4 py-2 border text-left font-semibold"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border)',
        color: 'var(--fg)',
      }}
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <td
      className="px-4 py-2 border"
      style={{
        borderColor: 'var(--border)',
        color: 'var(--fg)',
      }}
      {...props}
    >
      {children}
    </td>
  ),
};

export function MdxContent({ source }: { source: MDXRemoteSerializeResult }) {
  return <MDXRemote {...source} components={mdxComponents} />;
}

