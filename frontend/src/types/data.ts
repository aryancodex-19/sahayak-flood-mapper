export type SettlementStatus = "cut-off" | "accessible";

export interface Settlement {
  id: string;
  name: string;
  population: number;
  lat: number;
  lon: number;
  priorityScore: number;
  status: SettlementStatus;
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
}

export interface DataBundle {
  flood: FloodGeoJSON;
  settlements: Settlement[];
}

export type Language = "en" | "hi";
