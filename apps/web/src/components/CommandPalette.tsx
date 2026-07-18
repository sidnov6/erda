"use client";

import { Command } from "cmdk";

import { COMMANDS, type CommandDef } from "@/lib/registry";

/**
 * The ⌘K command line (§8.1): Bloomberg-style mnemonics behind an ERDA> prompt.
 * Styling per design-system skill — bg1 surface, hairline border, zero radius.
 */
export function CommandPalette({
  open,
  onClose,
  onRun,
}: {
  open: boolean;
  onClose: () => void;
  onRun: (cmd: CommandDef) => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-[rgba(12,10,7,0.72)]"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="mx-auto mt-[18vh] w-[520px] max-w-[calc(100vw-32px)] border border-line bg-bg1"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="ERDA command line" loop>
          <div className="flex h-10 items-center gap-2 border-b border-line px-3">
            <span className="font-mono text-[13px] text-gold">ERDA&gt;</span>
            <Command.Input
              autoFocus
              placeholder="type a mnemonic…"
              className="numeric w-full bg-transparent text-[13px] text-ink caret-gold placeholder:text-ink-faint focus:outline-none"
            />
          </div>
          <Command.List className="max-h-[320px] overflow-y-auto p-1">
            <Command.Empty className="px-2 py-3 font-mono text-[11px] text-ink-faint">
              UNKNOWN MNEMONIC — HELP LISTS COMMANDS
            </Command.Empty>
            {COMMANDS.map((cmd) => (
              <Command.Item
                key={cmd.mnemonic}
                value={cmd.mnemonic}
                keywords={[cmd.name]}
                onSelect={() => onRun(cmd)}
                className="flex h-8 cursor-pointer items-center gap-3 px-2 data-[selected=true]:bg-line/40"
              >
                <span className="w-14 shrink-0 font-mono text-[12px] text-gold">
                  {cmd.mnemonic}
                </span>
                <span className="flex-1 truncate text-[12px] text-ink">{cmd.name}</span>
                <span className="chip shrink-0 text-ink-faint">
                  {cmd.target ? "NO FEED" : cmd.phase}
                </span>
              </Command.Item>
            ))}
          </Command.List>
          <div className="flex h-6 items-center border-t border-line px-3 font-mono text-[11px] tracking-[0.06em] text-ink-faint">
            ↑↓ NAVIGATE · ↵ EXECUTE · ESC DISMISS
          </div>
        </Command>
      </div>
    </div>
  );
}
