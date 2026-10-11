import { useState, useMemo } from "react";
import { AppShell } from "@/components/app-shell";
import { Hero } from "@/components/hero";
import { StatsRow } from "@/components/stats-row";
import { FloodMap } from "@/components/flood-map";
import { PriorityTable } from "@/components/priority-table";
import { SituationReport } from "@/components/situation-report";
import { LanguageContext } from "@/lib/language-context";
import { loadData, computeStats } from "@/data";
import { t as translate, type TranslationKey } from "@/lib/i18n";
import type { Language } from "@/types/data";

type View = "landing" | "dashboard";

export default function App() {
  const [view, setView] = useState<View>("landing");
  const [language, setLanguage] = useState<Language>("en");
  const [showFlood, setShowFlood] = useState(true);
  const [showSettlements, setShowSettlements] = useState(true);

  const data = useMemo(() => loadData(), []);
  const stats = useMemo(() => computeStats(data), [data]);

  const langValue = {
    language,
    setLanguage,
    t: (key: TranslationKey) => translate(language, key),
  };

  if (view === "landing") {
    return (
      <LanguageContext.Provider value={langValue}>
        <Hero onViewMap={() => setView("dashboard")} />
      </LanguageContext.Provider>
    );
  }

  return (
    <LanguageContext.Provider value={langValue}>
      <AppShell
        language={language}
        onLanguageChange={setLanguage}
        showFlood={showFlood}
        onShowFloodChange={setShowFlood}
        showSettlements={showSettlements}
        onShowSettlementsChange={setShowSettlements}
        onBackToHome={() => setView("landing")}
      >
        <StatsRow stats={stats} />
        <FloodMap flood={data.flood} settlements={data.settlements} showFlood={showFlood} showSettlements={showSettlements} />
        <PriorityTable settlements={data.settlements} />
        <SituationReport data={data} stats={stats} language={language} />
      </AppShell>
    </LanguageContext.Provider>
  );
}