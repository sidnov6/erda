/** The signature element (§13.1): a thin seismic-wiggle trace under panel titles. */
export function SeismicDivider() {
  return (
    <svg
      className="w-full shrink-0"
      width="100%"
      height="8"
      viewBox="0 0 240 8"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M0 4 H28 C32 4 33 1.5 36 1.5 S40 6.5 43 6.5 47 4 50 4 H92
           C96 4 97 2 100 2 S104 6 107 6 111 4 114 4 H164
           C168 4 169 2.5 172 2.5 S176 5.5 179 5.5 183 4 186 4 H240"
        fill="none"
        stroke="var(--line)"
        strokeWidth="1"
      />
    </svg>
  );
}
