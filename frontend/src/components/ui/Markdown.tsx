import { memo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { cx } from "@/lib/cx";
import { parseCiteHref } from "@/lib/markers";
import { CodeBlock } from "./CodeBlock";

export interface MarkdownProps {
  source: string | null | undefined;
  className?: string;
  inline?: boolean;
  /** Renders a citation chip for a marker link produced by prepareMarkers(). */
  renderCitation?: (type: string, id: string) => ReactNode;
}

/** react-markdown + GFM + sanitise; links open in a new tab with noopener. */
export const Markdown = memo(function Markdown({ source, className, inline, renderCitation }: MarkdownProps) {
  if (!source) return null;
  const components: Components = {
    a({ href, children }) {
      const cite = parseCiteHref(href);
      if (cite) return renderCitation ? <>{renderCitation(cite.type, cite.id)}</> : null;
      const internal = href?.startsWith("/") && !href.startsWith("//");
      return (
        <a href={href} {...(internal ? {} : { target: "_blank", rel: "noopener noreferrer" })}>
          {children}
        </a>
      );
    },
    pre({ children }) {
      return <>{children}</>;
    },
    code({ className: cls, children }) {
      const text = String(children ?? "");
      const lang = /language-(\w+)/.exec(cls ?? "")?.[1];
      const block = Boolean(lang) || text.includes("\n");
      if (!block) return <code>{children}</code>;
      return <CodeBlock code={text.replace(/\n$/, "")} lang={lang} />;
    },
    ...(inline ? { p: ({ children }) => <>{children}</> } : {}),
  };
  const Wrapper = inline ? "span" : "div";
  return (
    <Wrapper className={cx(!inline && "k-prose", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]} components={components}>
        {source}
      </ReactMarkdown>
    </Wrapper>
  );
});
