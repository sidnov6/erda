"use client";

/**
 * The prospectivity map hero (§13.4). deck.gl over a self-hosted, offline
 * Natural Earth basemap (§15: no external tiles — the demo never breaks).
 *
 * HONEST BOUNDARY (§9.8): no prospectivity heatmap ships — the falsification
 * gate failed. This map shows wells + infrastructure + protected-area context
 * and drives the memo flow; it never claims where oil is. That statement is on
 * the map's own legend.
 *
 * Layers: well scatter (industry colors green oil / red gas / grey dry, filtered
 * by a spud-year time slider) · GEM infrastructure (toggle) · WDPA marine areas
 * (toggle). Click a point → block card → Generate memo (SSE) → /memos.
 */

import type { Layer } from "@deck.gl/core";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { useErdaOnce } from "@/lib/api";
import { BlockCard, type PickedBlock } from "./BlockCard";
import { MapControls } from "./MapControls";

// Fully self-contained basemap (§15: demo runs offline). No external tiles —
// a background-only maplibre style, with land drawn as a deck.gl GeoJsonLayer
// from a bundled Natural Earth 110m polygon set. Works with no internet.
const BLANK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#0C0A07" } }],
};

// §13.1 tokens as RGB — deck.gl wants resolved colors. Industry map convention:
// green oil / red gas / grey dry (experts notice this).
const OUTCOME_COLOR: Record<number, [number, number, number]> = {
  2: [63, 166, 106], //  oil → --oil (green)
  1: [214, 69, 80], //   gas → --gas (red)
  3: [90, 120, 105], //  discovery, phase unrecorded → muted green
  0: [110, 101, 88], //  dry hole → --dry (grey)
  [-1]: [59, 45, 35], // no recorded outcome → near-bg, dim
};
const CYAN: [number, number, number] = [95, 179, 201]; // --cyan infra/water
const GOLD: [number, number, number] = [232, 163, 61]; // --gold: known global fields (GOGET)

interface WellsPayload {
  available: boolean;
  n: number;
  lon: number[];
  lat: number[];
  outcome: number[];
  spud_year: number[];
}
interface InfraPayload {
  available: boolean;
  pipelines: { lon: number[]; lat: number[]; kind: string[]; n: number };
  terminals: { lon: number; lat: number; name: string; kind: string }[];
}
interface ProtectedPayload {
  available: boolean;
  n: number;
  geojson: GeoJSON.FeatureCollection;
}
interface FieldsPayload {
  available: boolean;
  n: number;
  lon: number[];
  lat: number[];
  phase: string[];
}
interface MapMeta {
  well_time_range: { min: number | null; max: number | null };
}

interface WellPoint {
  position: [number, number];
  outcome: number;
  year: number;
  index: number;
}

export function MapHero() {
  const holder = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const fittedRef = useRef(false);

  const { data: wells } = useErdaOnce<WellsPayload>("map/wells");
  const { data: meta } = useErdaOnce<MapMeta>("map/meta");
  const [land, setLand] = useState<GeoJSON.FeatureCollection | null>(null);
  useEffect(() => {
    fetch("/land-110m.json")
      .then((r) => r.json())
      .then((g: GeoJSON.FeatureCollection) => setLand(g))
      .catch(() => setLand(null));
  }, []);
  const [showFields, setShowFields] = useState(true); // global GOGET fields on by default
  const [showInfra, setShowInfra] = useState(false);
  const [showProtected, setShowProtected] = useState(false);
  const { data: fields } = useErdaOnce<FieldsPayload>(showFields ? "map/fields" : null);
  const { data: infra } = useErdaOnce<InfraPayload>(showInfra ? "map/infra" : null);
  const { data: protectedAreas } = useErdaOnce<ProtectedPayload>(
    showProtected ? "map/protected" : null
  );

  const [year, setYear] = useState(2026);
  const [picked, setPicked] = useState<PickedBlock | null>(null);

  const yearMin = meta?.well_time_range.min ?? 1966;
  const yearMax = meta?.well_time_range.max ?? 2026;
  useEffect(() => {
    if (meta?.well_time_range.max) setYear(meta.well_time_range.max);
  }, [meta]);

  // one-time map setup
  useEffect(() => {
    const el = holder.current;
    if (!el || mapRef.current) return;
    const map = new maplibregl.Map({
      container: el,
      style: BLANK_STYLE,
      // Global pre-load view. The open wildcat-outcome record spans three
      // regulator theatres — US Gulf of Mexico, NW Europe, and Australia — so
      // the camera must open on the world, not one basin. fitBounds() below
      // snaps it to the actual data extent once wells arrive.
      center: [18, 25],
      zoom: 1,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      overlay.finalize();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  // Snap the camera to the real data extent, once, when the first layer loads.
  // Wells span three regulator theatres (GoM / NW Europe / Australia) and the
  // GOGET fields are global — so fitting to their union opens the whole world
  // instead of one basin.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || fittedRef.current) return;
    let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
    const scan = (lon?: number[], lat?: number[]) => {
      if (!lon || !lat) return;
      for (let i = 0; i < lon.length; i++) {
        if (lon[i] < minLon) minLon = lon[i];
        if (lon[i] > maxLon) maxLon = lon[i];
        if (lat[i] < minLat) minLat = lat[i];
        if (lat[i] > maxLat) maxLat = lat[i];
      }
    };
    if (wells?.available) scan(wells.lon, wells.lat);
    if (showFields && fields?.available) scan(fields.lon, fields.lat);
    if (Number.isFinite(minLon) && maxLon > minLon) {
      map.fitBounds(
        [
          [minLon, minLat],
          [maxLon, maxLat],
        ],
        { padding: 36, duration: 0, maxZoom: 4 }
      );
      fittedRef.current = true;
    }
  }, [wells, fields, showFields]);

  // rebuild deck layers when data / filters change
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;

    const wellData: WellPoint[] = [];
    if (wells?.available) {
      for (let i = 0; i < wells.n; i++) {
        if (wells.spud_year[i] <= year) {
          wellData.push({
            position: [wells.lon[i], wells.lat[i]],
            outcome: wells.outcome[i],
            year: wells.spud_year[i],
            index: i,
          });
        }
      }
    }

    const layers: Layer[] = [];

    // land basemap — filled panel-tone, hairline coast. Under everything.
    if (land) {
      layers.push(
        new GeoJsonLayer({
          id: "land",
          data: land,
          stroked: true,
          filled: true,
          getFillColor: [20, 17, 12], // --bg1
          getLineColor: [74, 66, 54], // a warm grey above --line so coasts register
          lineWidthMinPixels: 0.8,
          pickable: false,
        })
      );
    }

    // Global oil & gas fields (GEM GOGET) — gold, drawn beneath the regulator
    // wildcat wells so the two layers stay visually distinct. Gold = a known
    // field somewhere on Earth; green/red/grey = a wildcat outcome from an open
    // regulator. Not a model, not a heatmap.
    if (showFields && fields?.available) {
      const fieldData = fields.lon.map((lon, i) => ({
        position: [lon, fields.lat[i]] as [number, number],
      }));
      layers.push(
        new ScatterplotLayer({
          id: "fields",
          data: fieldData,
          getPosition: (d: { position: [number, number] }) => d.position,
          getFillColor: [...GOLD, 205] as [number, number, number, number],
          getRadius: 2,
          radiusMinPixels: 1.3,
          radiusMaxPixels: 3.5,
          stroked: false,
          pickable: false,
        })
      );
    }

    if (showProtected && protectedAreas?.available) {
      layers.push(
        new GeoJsonLayer({
          id: "protected",
          data: protectedAreas.geojson,
          stroked: true,
          filled: true,
          getFillColor: [95, 179, 201, 26],
          getLineColor: [95, 179, 201, 120],
          lineWidthMinPixels: 0.5,
          pickable: false,
        })
      );
    }

    if (showInfra && infra?.available) {
      layers.push(
        new ScatterplotLayer({
          id: "infra-pipes",
          data: infra.pipelines.lon.map((lon, i) => ({
            position: [lon, infra.pipelines.lat[i]] as [number, number],
          })),
          getPosition: (d: { position: [number, number] }) => d.position,
          getFillColor: [95, 179, 201, 90],
          getRadius: 1,
          radiusMinPixels: 0.6,
          radiusMaxPixels: 1.5,
          pickable: false,
        })
      );
      layers.push(
        new ScatterplotLayer({
          id: "infra-terminals",
          data: infra.terminals,
          getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat],
          getFillColor: CYAN,
          getRadius: 5,
          radiusMinPixels: 3,
          radiusMaxPixels: 7,
          stroked: true,
          getLineColor: [12, 10, 7],
          lineWidthMinPixels: 1,
          pickable: true,
        })
      );
    }

    layers.push(
      new ScatterplotLayer({
        id: "wells",
        data: wellData,
        getPosition: (d: WellPoint) => d.position,
        getFillColor: (d: WellPoint) => OUTCOME_COLOR[d.outcome] ?? OUTCOME_COLOR[-1],
        getRadius: 2,
        radiusMinPixels: 1.2,
        radiusMaxPixels: 4,
        pickable: true,
        updateTriggers: { getFillColor: [year] },
      })
    );

    overlay.setProps({ layers });
  }, [wells, fields, infra, protectedAreas, land, showFields, showInfra, showProtected, year]);

  // Block pick: in overlay mode maplibre owns interaction, so its click event
  // is the reliable source of a lon/lat — the whole basin is pickable acreage.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const handler = (e: maplibregl.MapMouseEvent) => {
      setPicked({ lon: e.lngLat.lng, lat: e.lngLat.lat });
    };
    map.on("click", handler);
    return () => {
      map.off("click", handler);
    };
  }, []);

  return (
    <div className="relative h-full w-full">
      <div ref={holder} className="h-full w-full" />
      <MapControls
        year={year}
        yearMin={yearMin}
        yearMax={yearMax}
        onYear={setYear}
        showFields={showFields}
        onToggleFields={() => setShowFields((v) => !v)}
        showInfra={showInfra}
        onToggleInfra={() => setShowInfra((v) => !v)}
        showProtected={showProtected}
        onToggleProtected={() => setShowProtected((v) => !v)}
        wellCount={wells?.available ? wells.n : 0}
        fieldCount={showFields && fields?.available ? fields.n : 0}
      />
      {picked && <BlockCard block={picked} onClose={() => setPicked(null)} />}
    </div>
  );
}
