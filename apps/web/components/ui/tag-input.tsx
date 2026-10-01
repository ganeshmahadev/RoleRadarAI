"use client";

import { useId, useState } from "react";

import { focusRing, inputClass } from "./styles";

interface Props {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  hint?: string;
  maxItems?: number;
}

/** Free-text list editor: Enter or comma adds an item, each item has its own remove button. */
export function TagInput({ label, values, onChange, placeholder, hint, maxItems = 50 }: Props) {
  const id = useId();
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const items = raw
      .split(",")
      .map((v) => v.trim().slice(0, 100))
      .filter(Boolean);
    const next = [...values];
    for (const item of items) {
      if (next.length >= maxItems) break;
      if (!next.some((v) => v.toLowerCase() === item.toLowerCase())) next.push(item);
    }
    onChange(next);
    setDraft("");
  };

  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      {values.length > 0 && (
        <ul className="flex flex-wrap gap-1" aria-label={label}>
          {values.map((value) => (
            <li
              key={value}
              className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 text-xs"
            >
              {value}
              <button
                type="button"
                onClick={() => onChange(values.filter((v) => v !== value))}
                aria-label={`Remove ${value}`}
                className={`rounded px-0.5 text-muted hover:text-danger ${focusRing}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={id}
        value={draft}
        placeholder={placeholder}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if ((event.key === "Enter" || event.key === ",") && draft.trim()) {
            event.preventDefault();
            add(draft);
          } else if (event.key === "Backspace" && !draft && values.length) {
            onChange(values.slice(0, -1));
          }
        }}
        onBlur={() => draft.trim() && add(draft)}
        className={`${inputClass} w-full`}
      />
      {hint && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
