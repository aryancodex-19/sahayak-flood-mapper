import type { DataBundle, Settlement, FloodGeoJSON, DashboardStats, Scenario } from "@/types/data";

import realCutoffRaw from "./real_cutoff.json";
import realPracticalRaw from "./real_practical.json";
import realConnectedRaw from "./real_connected.json";
import realPriorityRaw from "./real_priority.json";
import realEventCutoffRaw from "./real_event_cutoff.json";
import realEventPracticalRaw from "./real_event_practical.json";

import mlCutoffRaw from "./ml_cutoff.json";
import mlPracticalRaw from "./ml_practical.json";
import mlConnectedRaw from "./ml_connected.json";
import mlPriorityRaw from "./ml_priority.json";
import mlFloodRaw from "./ml_flood.json";
import mlMetaRaw from "./ml_meta.json";

// Population mapping based on settlement classification
const POPULATION_MAP: Record<string, number> = {
  town: 5000,
  suburb: 3000,
  neighbourhood: 1500,
  village: 800,
  locality: 1000,
  hamlet: 200,
};

interface RawCutoffItem {
  id?: number | string;
  name: string;
  place_type?: string;
  type?: string;
  latitude: number;
  longitude: number;
  pre_flood_distance_km?: number;
}

interface RawPracticalItem {
  id?: number | string;
  name: string;
  place_type?: string;
  type?: string;
  latitude: number;
  longitude: number;
  pre_flood_distance_km?: number;
  post_flood_distance_km?: number;
  detour_ratio?: number;
  extra_distance_km?: number;
}

interface RawConnectedItem {
  id?: number | string;
  name: string;
  place_type?: string;
  type?: string;
  latitude: number;
  longitude: number;
  shortest_distance_km?: number;
  post_flood_distance_km?: number;
}

interface PriorityFeature {
  type: string;
  properties: {
    rank?: number;
    name: string;
    type?: string;
    population_est?: number;
    distance_km?: number;
    lat?: number;
    lon?: number;
    score?: number;
    category?: string;
    reason?: string;
  };
}

// Build map of pre-computed priority scores from priority_list.geojson for Severe baseline
const priorityFeatureMap = new Map<string, PriorityFeature["properties"]>();
if (realPriorityRaw && Array.isArray((realPriorityRaw as { features?: PriorityFeature[] }).features)) {
  for (const feature of (realPriorityRaw as { features: PriorityFeature[] }).features) {
    if (feature.properties?.name) {
      priorityFeatureMap.set(feature.properties.name, feature.properties);
    }
  }
}

// Build map of pre-computed priority scores from genuine ML U-Net priority ranking
const mlPriorityFeatureMap = new Map<string, PriorityFeature["properties"]>();
if (mlPriorityRaw && Array.isArray((mlPriorityRaw as { features?: PriorityFeature[] }).features)) {
  for (const feature of (mlPriorityRaw as { features: PriorityFeature[] }).features) {
    if (feature.properties?.name) {
      mlPriorityFeatureMap.set(feature.properties.name, feature.properties);
    }
  }
}

// Transform real, severe, or experimental ML data into Settlement models
function buildSettlements(scenario: Scenario = "severe"): Settlement[] {
  const result: Settlement[] = [];
  const isMl = scenario === "ml";
  const isReal = scenario === "real";

  // Determine datasets based on scenario
  const strictItems: RawCutoffItem[] = isMl
    ? (mlCutoffRaw as RawCutoffItem[]) || []
    : isReal
    ? (realEventCutoffRaw as RawCutoffItem[]) || []
    : (realCutoffRaw as RawCutoffItem[]) || [];

  const practicalItems: RawPracticalItem[] = isMl
    ? (mlPracticalRaw as RawPracticalItem[]) || []
    : isReal
    ? (realEventPracticalRaw as RawPracticalItem[]) || []
    : (realPracticalRaw as RawPracticalItem[]) || [];

  // For Real Event, all 104 settlements remain connected (0 strict, 0 practical cut-offs)
  const connectedItems: RawConnectedItem[] = isMl
    ? (mlConnectedRaw as RawConnectedItem[]) || []
    : isReal
    ? [
        ...((realCutoffRaw as RawConnectedItem[]) || []),
        ...((realPracticalRaw as RawConnectedItem[]) || []),
        ...((realConnectedRaw as RawConnectedItem[]) || []),
      ]
    : (realConnectedRaw as RawConnectedItem[]) || [];

  const activePriorityMap = isMl ? mlPriorityFeatureMap : priorityFeatureMap;

  // 1. Strict Cut-offs
  for (const item of strictItems) {
    const pInfo = activePriorityMap.get(item.name);
    const pType = (item.place_type || item.type || "village").toLowerCase();
    const pop = pInfo?.population_est ?? POPULATION_MAP[pType] ?? 800;
    const score = pInfo?.score ?? 50.0;
    const distanceKm = pInfo?.distance_km ?? item.pre_flood_distance_km ?? 5.0;

    result.push({
      id: `strict-${item.id ?? item.name}`,
      name: item.name,
      population: pop,
      lat: item.latitude,
      lon: item.longitude,
      priorityScore: score,
      status: "cut-off",
      statusType: "strict-cutoff",
      distanceToHospitalKm: Math.round(distanceKm * 10) / 10,
      isolatedSinceHours: 48,
    });
  }

  // 2. Practical Cut-offs
  for (const item of practicalItems) {
    const pType = (item.place_type || item.type || "suburb").toLowerCase();
    const pop = POPULATION_MAP[pType] ?? 800;
    const distanceKm = item.post_flood_distance_km ?? (item.pre_flood_distance_km ? item.pre_flood_distance_km * (item.detour_ratio ?? 3) : 25.0);

    // Score on standard formula: 40 + (0.4 * norm_pop) + (0.2 * norm_dist)
    const normPop = ((pop - 200) / (5000 - 200)) * 100;
    const normDist = Math.min(100, (distanceKm / 31.72) * 100);
    const score = Number((35.0 + 0.3 * normPop + 0.15 * normDist).toFixed(2));

    result.push({
      id: `practical-${item.id ?? item.name}`,
      name: item.name,
      population: pop,
      lat: item.latitude,
      lon: item.longitude,
      priorityScore: score,
      status: "cut-off",
      statusType: "practical-cutoff",
      distanceToHospitalKm: Math.round(distanceKm * 10) / 10,
      isolatedSinceHours: 24,
    });
  }

  // 3. Connected Settlements
  for (const item of connectedItems) {
    const pType = (item.place_type || item.type || "village").toLowerCase();
    const pop = POPULATION_MAP[pType] ?? 800;
    const rawDist = item.shortest_distance_km ?? item.post_flood_distance_km ?? 0.0;
    const distanceKm = rawDist > 0 ? rawDist : 1.5;
    const score = Number(Math.max(5.0, Math.min(35.0, (distanceKm / 31.72) * 35.0)).toFixed(2));

    result.push({
      id: `conn-${item.id ?? item.name}`,
      name: item.name,
      population: pop,
      lat: item.latitude,
      lon: item.longitude,
      priorityScore: score,
      status: "accessible",
      statusType: "connected",
      distanceToHospitalKm: Math.round(distanceKm * 10) / 10,
      isolatedSinceHours: 0,
    });
  }

  return result;
}

// Build flood extent FeatureCollection matching expected schema
function buildFloodExtent(scenario: Scenario = "severe"): FloodGeoJSON {
  if (scenario === "ml") {
    return mlFloodRaw as FloodGeoJSON;
  }

  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { id: "flood-sar-kamrup", areaHectares: 1950, confidence: 0.94 },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [91.45, 26.35],
              [91.55, 26.42],
              [91.75, 26.38],
              [91.85, 26.28],
              [91.82, 26.15],
              [91.68, 26.18],
              [91.52, 26.24],
              [91.45, 26.35],
            ],
          ],
        },
      },
      {
        type: "Feature",
        properties: { id: "flood-sar-choke-points", areaHectares: 480, confidence: 0.88 },
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [91.66, 26.29],
              [91.72, 26.33],
              [91.76, 26.30],
              [91.70, 26.26],
              [91.66, 26.29],
            ],
          ],
        },
      },
    ],
  };
}

export function loadData(scenario: Scenario = "severe"): DataBundle & { stats: DashboardStats } {
  const flood = buildFloodExtent(scenario);
  const settlements = buildSettlements(scenario);
  const stats = computeStats({ flood, settlements }, scenario);
  return {
    flood,
    settlements,
    stats,
  };
}

export function computeStats(data: DataBundle, scenario: Scenario = "severe"): DashboardStats {
  const { settlements } = data;
  
  // Cut-off settlements (strict + practical)
  const cutOffSettlements = settlements.filter((s) => s.status === "cut-off");
  const cutOffCount = cutOffSettlements.length;

  // Total affected population across cut-off settlements
  const affectedPopulation = cutOffSettlements.reduce((sum, s) => sum + s.population, 0);

  // Average priority score across cut-off settlements (or 0 if none)
  const avgPriority =
    cutOffSettlements.length > 0
      ? cutOffSettlements.reduce((sum, s) => sum + s.priorityScore, 0) / cutOffSettlements.length
      : 0;

  if (scenario === "ml") {
    return {
      floodAreaHectares: mlMetaRaw.flood_area_hectares,
      cutOffCount,
      affectedPopulation,
      averagePriorityScore: Number(avgPriority.toFixed(2)),
      isExperimental: true,
      disclaimer: mlMetaRaw.disclaimer,
      floodedEdgesCount: mlMetaRaw.flooded_road_edges,
      floodedEdgesPct: mlMetaRaw.flooded_road_pct,
    };
  }

  return {
    floodAreaHectares: 1950,
    cutOffCount,
    affectedPopulation,
    averagePriorityScore: Number(avgPriority.toFixed(2)),
    isExperimental: false,
  };
}

export { mlMetaRaw };
