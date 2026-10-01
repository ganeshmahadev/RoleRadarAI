"use client";

import { useId, useRef, type ReactNode } from "react";

/**
 * Native popover menu (top layer, light dismiss, Esc to close) positioned under its trigger.
 * Clicking any button inside closes the menu.
 */
export function PopoverMenu({
  label,
  triggerClassName,
  triggerAriaLabel,
  children,
}: {
  label: ReactNode;
  triggerClassName: string;
  triggerAriaLabel: string;
  children: ReactNode;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);

  const position = (event: React.ToggleEvent<HTMLDivElement>) => {
    const menu = event.currentTarget;
    if (event.newState !== "open" || !trigger.current) return;
    const rect = trigger.current.getBoundingClientRect();
    menu.style.top = `${rect.bottom + 4}px`;
    menu.style.left = `${Math.max(8, rect.right - menu.offsetWidth)}px`;
  };

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={triggerClassName}
        popoverTarget={id}
        aria-label={triggerAriaLabel}
      >
        {label}
      </button>
      <div
        id={id}
        popover="auto"
        onToggle={position}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button")) {
            event.currentTarget.hidePopover?.();
          }
        }}
        className="fixed m-0 w-48 rounded border border-border bg-background p-1 text-foreground shadow-md"
      >
        {children}
      </div>
    </>
  );
}
