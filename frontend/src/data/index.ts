import type { DataBundle } from "@/types/data";
import { dummyFlood, dummySettlements } from "./dummy";

export function loadData(): DataBundle {
  return {
    flood: dummyFlood,
    settlements: dummySettlements,
  };
}

export function computeStats(data: DataBundle) {
  const { flood, settlements } = data;
  const floodAreaHectares = flood.features.reduce(
    (sum, f) => sum + f.properties.areaHectares,
    0
  );
  const cutOffSettlements = settlements.filter((s) => s.status === "cut-off");
  const cutOffCount = cutOffSettlements.length;
  const affectedPopulation = cutOffSettlements.reduce(
    (sum, s) => sum + s.population,
    0
  );
  const averagePriorityScore =
    settlements.length > 0
      ? settlements.reduce((sum, s) => sum + s.priorityScore, 0) /
        settlements.length
      : 0;
  return {
    floodAreaHectares: Math.round(floodAreaHectares),
    cutOffCount,
    affectedPopulation,
    averagePriorityScore: Number(averagePriorityScore.toFixed(2)),
  };
}
