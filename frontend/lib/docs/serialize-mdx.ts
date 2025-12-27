import { serialize } from 'next-mdx-remote/serialize';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { MDXRemoteSerializeResult } from 'next-mdx-remote';

export async function serializeMdx(source: string): Promise<MDXRemoteSerializeResult> {
  return serialize(source, {
    mdxOptions: {
      remarkPlugins: [remarkGfm],
      rehypePlugins: [rehypeRaw],
    },
  });
}


