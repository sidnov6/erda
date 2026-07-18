import { SeismicDivider } from "./SeismicDivider";
import type { PanelDef } from "@/lib/registry";

/**
 * Panel chrome per the design-system skill §3: title bar with mnemonic tag,
 * seismic-wiggle divider, body on --bg1, freshness badge slot. Gold appears on
 * the mnemonic (command affordance) and on the border only while active.
 */
export function Panel({
  def,
  active,
  children,
}: {
  def: PanelDef;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={def.title}
      className={`panel flex h-full flex-col overflow-hidden ${active ? "panel--active" : ""}`}
    >
      <header className="panel-drag flex h-6 shrink-0 cursor-grab select-none items-center justify-between px-2">
        <h2 className="panel-title">{def.title}</h2>
        <div className="flex items-center gap-2">
          <span className="chip text-ink-faint">NO FEED</span>
          <span className="panel-mnemo text-[11px]">{def.mnemonic}</span>
        </div>
      </header>
      <SeismicDivider />
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}
