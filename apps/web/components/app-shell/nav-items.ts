/** Sidebar entries. Only routes that exist are listed (no placeholder navigation). */
export const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/companies", label: "Companies" },
  { href: "/eures", label: "EURES Queue" },
  { href: "/jobs", label: "Jobs" },
  { href: "/matches", label: "Matches" },
  { href: "/settings/profile", label: "Settings" },
] as const;
