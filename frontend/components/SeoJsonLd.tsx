/**
 * Reusable server-rendered JSON-LD structured data component
 * 
 * This component renders JSON-LD structured data for SEO.
 * It must be server-rendered (not marked 'use client').
 * 
 * Usage:
 *   <SeoJsonLd schema={schemaObject} />
 */
interface SeoJsonLdProps {
  schema: object | object[];
}

export default function SeoJsonLd({ schema }: SeoJsonLdProps) {
  // Use @graph format if multiple schemas are provided
  const schemaData = Array.isArray(schema)
    ? {
        "@context": "https://schema.org",
        "@graph": schema,
      }
    : schema;

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(schemaData, null, 0),
      }}
    />
  );
}
