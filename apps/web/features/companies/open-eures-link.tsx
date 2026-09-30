import { focusRing } from "@/components/ui/styles";
import type { Company } from "@/lib/api/companies";

/** Opens the company-specific EURES search in a new tab. RoleRadarAI never fetches EURES. */
export function OpenEuresLink({ company, onOpen }: { company: Company; onOpen?: () => void }) {
  return (
    <a
      href={company.eures_search_url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onOpen}
      aria-label={`Open EURES search for ${company.company_name} (opens in new tab)`}
      className={`whitespace-nowrap rounded text-sm font-medium text-accent hover:underline ${focusRing}`}
    >
      Open EURES ↗
    </a>
  );
}
