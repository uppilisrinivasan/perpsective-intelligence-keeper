import { urls } from "@/api/client";
import { cx } from "@/lib/cx";

/** The generated SVG avatar (/avatars/{id}.svg); decorative when a name is shown next to it. */
export function PersonAvatar({ personId, size = "md", label }: { personId: string | null | undefined; size?: "xs" | "sm" | "md" | "lg"; label?: string }) {
  const cls = size === "xs" ? "size-4" : size === "sm" ? "size-5" : size === "md" ? "size-7" : "size-10";
  if (!personId) return <span className={cx("inline-block shrink-0 rounded-full bg-surface-2", cls)} aria-hidden />;
  return <img src={urls.avatar(personId)} alt={label ?? ""} className={cx("inline-block shrink-0 rounded-full bg-surface-2", cls)} loading="lazy" decoding="async" />;
}
