import { useState, useMemo } from "react";
import { AppShell } from "@/components/app-shell";
import { Hero } from "@/components/hero";
import { StatsRow } from "@/components/stats-row";
import { FloodMap } from "@/components/flood-map";
import { PriorityTable } from "@/components/priority-table";
import { SituationReport } from "@/components/situation-report";
import { loadData, computeStats } from "@/data";
import type { Scenario } from "@/types/data";

type View = "landing" | "dashboard";

export default function App() {
  const [view, setView] = useState<View>("landing");
  const [scenario, setScenario] = useState<Scenario>("severe");
  const [showFlood, setShowFlood] = useState(true);
  const [showSettlements, setShowSettlements] = useState(true);

  const data = useMemo(() => loadData(scenario), [scenario]);
  const stats = useMemo(() => computeStats(data), [data]);

  if (view === "landing") {
    return <Hero onViewMap={() => setView("dashboard")} />;
  }

  return (
    <AppShell
      scenario={scenario}
      onScenarioChange={setScenario}
      language="en"
      onLanguageChange={() => {}}
      showFlood={showFlood}
      onShowFloodChange={setShowFlood}
      showSettlements={showSettlements}
      onShowSettlementsChange={setShowSettlements}
      onBackToHome={() => setView("landing")}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Kamrup Flood Intelligence</h1>
          <p className="text-xs text-muted-foreground">Satellite SAR monitoring & rescue prioritization</p>
        </div>
        <div className="inline-flex rounded-lg border border-border bg-card/60 p-1 backdrop-blur-md">
          <button
            type="button"
            onClick={() => setScenario("severe")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              scenario === "severe"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Severe Scenario
          </button>
          <button
            type="button"
            onClick={() => setScenario("real")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              scenario === "real"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Real Event
          </button>
        </div>
      </div>
      <StatsRow stats={stats} />
      <FloodMap flood={data.flood} settlements={data.settlements} showFlood={showFlood} showSettlements={showSettlements} />
      <PriorityTable settlements={data.settlements} />
      <SituationReport data={data} stats={stats} language="en" />
    </AppShell>
  );
}