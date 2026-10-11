import type { Settlement, FloodGeoJSON } from "@/types/data";

export const dummyFlood: FloodGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { id: "flood-01", areaHectares: 540, confidence: 0.91 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [91.45, 26.02],
            [91.48, 26.05],
            [91.52, 26.04],
            [91.51, 25.99],
            [91.46, 25.98],
            [91.45, 26.02],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { id: "flood-02", areaHectares: 320, confidence: 0.84 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [91.54, 26.07],
            [91.58, 26.09],
            [91.62, 26.06],
            [91.60, 26.02],
            [91.55, 26.03],
            [91.54, 26.07],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { id: "flood-03", areaHectares: 680, confidence: 0.93 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [91.42, 25.94],
            [91.46, 25.97],
            [91.50, 25.95],
            [91.49, 25.91],
            [91.44, 25.90],
            [91.42, 25.94],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { id: "flood-04", areaHectares: 410, confidence: 0.88 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [91.57, 25.98],
            [91.63, 26.01],
            [91.67, 25.97],
            [91.64, 25.93],
            [91.59, 25.94],
            [91.57, 25.98],
          ],
        ],
      },
    },
  ],
};

export const dummySettlements: Settlement[] = [
  { id: "s01", name: "Changsari", population: 400, lat: 26.08, lon: 91.42, priorityScore: 0.52, status: "cut-off", distanceToHospitalKm: 3, isolatedSinceHours: 48 },
  { id: "s02", name: "Bijoynagar", population: 850, lat: 26.08, lon: 91.48, priorityScore: 0.29, status: "cut-off", distanceToHospitalKm: 18, isolatedSinceHours: 24 },
  { id: "s03", name: "Dharamtul", population: 1200, lat: 26.08, lon: 91.55, priorityScore: 0.61, status: "cut-off", distanceToHospitalKm: 7, isolatedSinceHours: 60 },
  { id: "s04", name: "Nagarbera", population: 2400, lat: 26.08, lon: 91.62, priorityScore: 0.30, status: "cut-off", distanceToHospitalKm: 22, isolatedSinceHours: 12 },
  { id: "s05", name: "Palashbari", population: 320, lat: 26.04, lon: 91.44, priorityScore: 0.63, status: "cut-off", distanceToHospitalKm: 5, isolatedSinceHours: 72 },
  { id: "s06", name: "Chaygaon", population: 560, lat: 26.04, lon: 91.51, priorityScore: 0.37, status: "cut-off", distanceToHospitalKm: 14, isolatedSinceHours: 36 },
  { id: "s07", name: "Boko", population: 1800, lat: 26.04, lon: 91.58, priorityScore: 0.25, status: "cut-off", distanceToHospitalKm: 20, isolatedSinceHours: 8 },
  { id: "s08", name: "Sonapur", population: 150, lat: 26.04, lon: 91.65, priorityScore: 0.59, status: "cut-off", distanceToHospitalKm: 4, isolatedSinceHours: 66 },
  { id: "s09", name: "Hajo", population: 950, lat: 26.00, lon: 91.42, priorityScore: 0.41, status: "cut-off", distanceToHospitalKm: 9, isolatedSinceHours: 30 },
  { id: "s10", name: "Rangia", population: 2100, lat: 26.00, lon: 91.49, priorityScore: 0.56, status: "cut-off", distanceToHospitalKm: 16, isolatedSinceHours: 54 },
  { id: "s11", name: "Sualkuchi", population: 700, lat: 26.00, lon: 91.56, priorityScore: 0.35, status: "cut-off", distanceToHospitalKm: 6, isolatedSinceHours: 18 },
  { id: "s12", name: "Kamalpur", population: 3200, lat: 26.00, lon: 91.63, priorityScore: 0.51, status: "cut-off", distanceToHospitalKm: 24, isolatedSinceHours: 42 },
  { id: "s13", name: "Jagiroad", population: 450, lat: 25.96, lon: 91.45, priorityScore: 0.21, status: "cut-off", distanceToHospitalKm: 12, isolatedSinceHours: 6 },
  { id: "s14", name: "Baihata", population: 1600, lat: 25.96, lon: 91.52, priorityScore: 0.57, status: "cut-off", distanceToHospitalKm: 8, isolatedSinceHours: 50 },
  { id: "s15", name: "Nalbari", population: 2800, lat: 25.96, lon: 91.59, priorityScore: 0.44, status: "accessible", distanceToHospitalKm: 19, isolatedSinceHours: 28 },
  { id: "s16", name: "Tihu", population: 380, lat: 25.96, lon: 91.66, priorityScore: 0.53, status: "accessible", distanceToHospitalKm: 11, isolatedSinceHours: 62 },
  { id: "s17", name: "Goreshwar", population: 1100, lat: 25.92, lon: 91.43, priorityScore: 0.42, status: "accessible", distanceToHospitalKm: 15, isolatedSinceHours: 40 },
  { id: "s18", name: "Rampur", population: 650, lat: 25.92, lon: 91.50, priorityScore: 0.32, status: "accessible", distanceToHospitalKm: 10, isolatedSinceHours: 20 },
  { id: "s19", name: "Barpeta Road", population: 2900, lat: 25.92, lon: 91.57, priorityScore: 0.60, status: "accessible", distanceToHospitalKm: 21, isolatedSinceHours: 58 },
  { id: "s20", name: "Howly", population: 520, lat: 25.92, lon: 91.64, priorityScore: 0.37, status: "accessible", distanceToHospitalKm: 13, isolatedSinceHours: 34 },
  { id: "s21", name: "Mirza", population: 1900, lat: 25.88, lon: 91.46, priorityScore: 0.50, status: "accessible", distanceToHospitalKm: 17, isolatedSinceHours: 46 },
  { id: "s22", name: "Singra", population: 750, lat: 25.88, lon: 91.53, priorityScore: 0.20, status: "accessible", distanceToHospitalKm: 23, isolatedSinceHours: 16 },
];
