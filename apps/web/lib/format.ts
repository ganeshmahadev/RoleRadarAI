const dateFormat = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });
const dateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
});

export const formatDate = (iso: string | null) => (iso ? dateFormat.format(new Date(iso)) : "—");
export const formatDateTime = (iso: string | null) =>
  iso ? dateTimeFormat.format(new Date(iso)) : "—";
