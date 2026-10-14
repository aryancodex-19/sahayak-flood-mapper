import { useState, useMemo } from "react";
import { AppShell } from "@/components/app-shell";
import { Hero } from "@/components/hero";
import { StatsRow } from "@/components/stats-row";
import { FloodMap } from "@/components/flood-map";
import { PriorityTable } from "@/components/priority-table";
import { SituationReport } from "@/components/situation-report";
import { loadData, computeStats } from "@/data";
import { LanguageContext } from "@/lib/language-context";
import { translations, type TranslationKey } from "@/lib/i18n";
import type { Language, Scenario } from "@/types/data";

type View = "landing" | "dashboard";
type Page = "overview" | "map" | "priority" | "report";

export default function App() {
  const [view, setView] = useState<View>("landing");
  const [scenario, setScenario] = useState<Scenario>("severe");
  const [showFlood, setShowFlood] = useState(true);
  const [showSettlements, setShowSettlements] = useState(true);
  const [language, setLanguage] = useState<Language>("en");
  const [activePage, setActivePage] = useState<Page>("overview");

  const data = useMemo(() => loadData(scenario), [scenario]);
  const stats = useMemo(() => computeStats(data, scenario), [data, scenario]);

  const languageValue = {
    language,
    setLanguage,
    t: (key: TranslationKey) => translations[language][key],
  };

  if (view === "landing") {
    return (
      <LanguageContext.Provider value={languageValue}>
        <Hero onViewMap={() => setView("dashboard")} />
      </LanguageContext.Provider>
    );
  }

  return (
    <LanguageContext.Provider value={languageValue}>
      <AppShell
        scenario={scenario}
        onScenarioChange={setScenario}
        language={language}
        onLanguageChange={setLanguage}
        showFlood={showFlood}
        onShowFloodChange={setShowFlood}
        showSettlements={showSettlements}
        onShowSettlementsChange={setShowSettlements}
        onBackToHome={() => setView("landing")}
        activePage={activePage}
        onPageChange={setActivePage}
      >
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold tracking-tight">Kamrup Flood Intelligence</h1>
          <p className="text-xs text-muted-foreground">Satellite SAR monitoring & rescue prioritization</p>
        </div>

        {scenario === "ml" && (
          <div className="rounded-lg border border-purple-500/30 bg-purple-500/10 p-3.5 text-xs text-purple-200 shadow-sm">
            <div className="flex items-center gap-2 font-semibold text-purple-300">
              <span className="h-2 w-2 rounded-full bg-purple-400 animate-pulse" />
              Experimental Model Prediction — Sentinel-1 SAR U-Net + ResNet34
            </div>
            <p className="mt-1 text-purple-200/80 leading-relaxed">
              Preliminary deep-learning predictions trained against Sentinel-1 SAR weak pseudo-labels (June 2022 Kamrup scene).
              Evaluated 20,669 road edges with 6,306 submerged segments (30.51%) and 20 cut-off settlements.
              <strong className="text-purple-100 ml-1">Predictions are experimental and not independently ground-truth validated.</strong>
            </p>
          </div>
        )}

        {activePage === "overview" && (
          <>
            <StatsRow stats={stats} />
            <FloodMap key={scenario} flood={data.flood} settlements={data.settlements} showFlood={showFlood} showSettlements={showSettlements} />
            <PriorityTable settlements={data.settlements} />
            <SituationReport data={data} stats={stats} language={language} />
          </>
        )}
        {activePage === "map" && (
          <FloodMap flood={data.flood} settlements={data.settlements} showFlood={showFlood} showSettlements={showSettlements} />
        )}
        {activePage === "priority" && (
          <PriorityTable settlements={data.settlements} />
        )}
        {activePage === "report" && (
          <SituationReport data={data} stats={stats} language={language} />
        )}
      </AppShell>
    </LanguageContext.Provider>
  );
}
