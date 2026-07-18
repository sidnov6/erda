/**
 * Status line + honest-boundaries footer (§1: boundaries print in the UI footer;
 * §15: the mode badge tells the truth — P0 has no data plane, so it reads SHELL).
 */
export function StatusFooter({ status }: { status: string }) {
  return (
    <footer className="flex h-8 shrink-0 items-center gap-3 border-t border-line bg-bg0 px-2">
      <span className="numeric truncate text-[11px] text-ink-dim" role="status">
        {status}
      </span>
      <div className="min-w-0 flex-1" />
      <span className="hidden truncate text-[11px] text-ink-faint md:inline">
        Screening tool — ranks resemblance to historically successful acreage. Not seismic; never
        &ldquo;oil is here.&rdquo;
      </span>
      <span className="chip shrink-0 text-ink-faint">SHELL · NO DATA</span>
      <span className="chip shrink-0 text-ink-faint">P0</span>
    </footer>
  );
}
