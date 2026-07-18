/**
 * Panel + command registries for the terminal shell (spec §8.1, §13.2).
 * P0: panels are empty shells with honest "awaiting feed" states — no fabricated
 * numbers anywhere. `phase` records when the real feed/feature lands (§14).
 * Ghost skeletons draw each panel's future frame (schema, never values).
 */

export type PanelId = "crv" | "inv" | "opec" | "map" | "disc" | "rank" | "events";
export type PanelKind = "chart" | "table" | "feed" | "map";

export interface PanelDef {
  id: PanelId;
  mnemonic: string;
  title: string;
  /** Honest empty-state note: which sources connect, and in which phase. */
  feedNote: string;
  /** Optional expansion of feedNote, shown as a tooltip. */
  feedDetail?: string;
  kind: PanelKind;
  /** Future column schema for table panels — schema is honest, values would not be. */
  columns?: string[];
  hero?: boolean;
  layout: { x: number; y: number; w: number; h: number; minW: number; minH: number };
}

export const PANELS: PanelDef[] = [
  {
    id: "crv",
    mnemonic: "CRV",
    title: "Price & curve deck",
    feedNote: "FRED · YF_CURVE — P1",
    kind: "chart",
    layout: { x: 0, y: 0, w: 3, h: 6, minW: 2, minH: 3 },
  },
  {
    id: "inv",
    mnemonic: "INV",
    title: "Inventories",
    feedNote: "EIA WPSR · JODI — P1",
    kind: "chart",
    layout: { x: 0, y: 6, w: 3, h: 5, minW: 2, minH: 3 },
  },
  {
    id: "opec",
    mnemonic: "OPEC",
    title: "OPEC+ compliance",
    feedNote: "OPEC MOMR — P1",
    kind: "table",
    columns: ["COUNTRY", "PLEDGED", "DELIVERED", "COMP %"],
    layout: { x: 0, y: 11, w: 3, h: 5, minW: 2, minH: 3 },
  },
  {
    id: "map",
    mnemonic: "MAP",
    title: "Prospectivity map",
    feedNote: "WELL DB — P2 · MODEL RASTER — P3",
    kind: "map",
    hero: true,
    layout: { x: 3, y: 0, w: 6, h: 16, minW: 4, minH: 8 },
  },
  {
    id: "disc",
    mnemonic: "DISC",
    title: "Discovery monitor",
    feedNote: "LABEL DB · 5 REGULATORS — P2",
    feedDetail: "SODIR · NSTA · NLOG · BOEM/BSEE · NOPIMS",
    kind: "chart",
    layout: { x: 9, y: 0, w: 3, h: 6, minW: 2, minH: 3 },
  },
  {
    id: "rank",
    mnemonic: "RANK",
    title: "Basin ranking",
    feedNote: "MODEL SCORES + SHAP — P3",
    kind: "table",
    columns: ["BASIN", "SCORE", "BAND", "TOP DRIVERS"],
    layout: { x: 9, y: 6, w: 3, h: 5, minW: 2, minH: 3 },
  },
  {
    id: "events",
    mnemonic: "EVENTS",
    title: "Event feed",
    feedNote: "GDELT — P1",
    kind: "feed",
    layout: { x: 9, y: 11, w: 3, h: 5, minW: 2, minH: 3 },
  },
];

export interface CommandDef {
  mnemonic: string;
  name: string;
  /** Panel focused when the command runs, if it maps onto the shell. */
  target?: PanelId;
  /** Phase tag shown when the command has no shell target yet (§14 vocabulary). */
  phase?: string;
  /** Status-line response when there is no target yet. */
  response?: string;
}

export const COMMANDS: CommandDef[] = [
  { mnemonic: "CRV", name: "Price & curve deck", target: "crv" },
  { mnemonic: "INV", name: "Inventories", target: "inv" },
  { mnemonic: "OPEC", name: "OPEC+ compliance", target: "opec" },
  {
    mnemonic: "RIG",
    name: "Rigs vs production",
    phase: "P1",
    response: "RIG — rigs/production panel connects in P1",
  },
  { mnemonic: "DISC", name: "Discovery monitor", target: "disc" },
  { mnemonic: "MAP", name: "Prospectivity map", target: "map" },
  {
    mnemonic: "MEMO",
    name: "Generate feasibility memo",
    phase: "P5",
    response: "MEMO <block|lat,lon> — committee arrives in P5",
  },
  {
    mnemonic: "VAL",
    name: "Validation report",
    phase: "P1",
    response: "VAL — /validation page arrives in P1",
  },
  {
    mnemonic: "HELP",
    name: "List commands",
    phase: "SHELL",
    response: "CRV · INV · OPEC · RIG · DISC · MAP <region> · MEMO <block> · VAL · HELP",
  },
];
