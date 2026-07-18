"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CommandPalette } from "./CommandPalette";
import { StatusFooter } from "./StatusFooter";
import { TopBar } from "./TopBar";
import { Workspace } from "./Workspace";
import { type SourceStatus, useErda } from "@/lib/api";
import type { CommandDef, PanelId } from "@/lib/registry";

const READY = "READY — ⌘K OPENS THE COMMAND LINE";

export default function Terminal() {
  const router = useRouter();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [focused, setFocused] = useState<PanelId | null>(null);
  const [status, setStatus] = useState(READY);
  const { data: sourcesData } = useErda<{ sources: SourceStatus[] }>("sources", 120_000);
  const sources = sourcesData
    ? Object.fromEntries(sourcesData.sources.map((s) => [s.source_id, s]))
    : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const runCommand = useCallback(
    (cmd: CommandDef) => {
      setPaletteOpen(false);
      if (cmd.href) {
        router.push(cmd.href);
        setStatus(`${cmd.mnemonic} — ${cmd.href}`);
      } else if (cmd.target) {
        setFocused(cmd.target);
        setStatus(`${cmd.mnemonic} — ${cmd.name.toUpperCase()} FOCUSED`);
      } else {
        setStatus(cmd.response ?? READY);
      }
    },
    [router]
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-bg0">
      <TopBar onOpenPalette={() => setPaletteOpen(true)} />
      <Workspace focused={focused} sources={sources} />
      <StatusFooter status={status} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onRun={runCommand}
      />
    </div>
  );
}
