export type SettlementStatus = "cut-off" | "accessible";
export type SettlementStatusType = "strict-cutoff" | "practical-cutoff" | "connected";
export type Scenario = "real" | "severe" | "ml";

export interface Settlement {
  id: string;
  name: string;
  population: number;
  lat: number;
  lon: number;
  priorityScore: number;
  status: SettlementStatus;
  statusType: SettlementStatusType;
  distanceToHospitalKm: number;
  isolatedSinceHours: number;
}

export interface FloodFeatureProperties {
  id: string;
  areaHectares: number;
  confidence: number;
}

export interface FloodFeature {
  type: "Feature";
  properties: FloodFeatureProperties;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
}

export interface FloodGeoJSON {
  type: "FeatureCollection";
  features: FloodFeature[];
}

export interface DashboardStats {
  floodAreaHectares: number;
  cutOffCount: number;
  affectedPopulation: number;
  averagePriorityScore: number;
  isExperimental?: boolean;
  disclaimer?: string;
  floodedEdgesCount?: number;
  floodedEdgesPct?: number;
}

export interface DataBundle {
  flood: FloodGeoJSON;
  settlements: Settlement[];
}

export type Language = "en" | "hi";
