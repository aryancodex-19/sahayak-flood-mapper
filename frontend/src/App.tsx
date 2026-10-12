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
  const stats = useMemo(() => computeStats(data), [data]);

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
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Kamrup Flood Intelligence</h1>
          <p className="text-xs text-muted-foreground">Satellite SAR monitoring & rescue prioritization</p>
        </div>
        {activePage === "overview" && (
          <>
            <StatsRow stats={stats} />
            <FloodMap flood={data.flood} settlements={data.settlements} showFlood={showFlood} showSettlements={showSettlements} />
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
