import type { MouseEvent } from "react";

/**
 * Scrolls only the results list to a section. A plain anchor jump also scrolls the
 * panel around the list, which pushed the panel header (full screen, edit) out of view.
 */
export function jumpTo(event: MouseEvent<HTMLAnchorElement>, id: string) {
  const target = document.getElementById(id);
  const list = target?.closest<HTMLElement>(".map-results-scroll");
  if (!target || !list) return;
  event.preventDefault();
  const top = target.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop - 12;
  const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  list.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
  target.focus({ preventScroll: true });
}
