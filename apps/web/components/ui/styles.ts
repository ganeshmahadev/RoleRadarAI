/** Shared Tailwind class strings for the few primitives used across features. */
export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export const inputClass = `h-8 rounded border border-border bg-background px-2 text-sm ${focusRing}`;

export const buttonClass = `inline-flex h-8 items-center gap-1 rounded border border-border bg-background px-3 text-sm font-medium hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50 ${focusRing}`;

export const primaryButtonClass = `inline-flex h-8 items-center gap-1 rounded bg-accent px-3 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 ${focusRing}`;
