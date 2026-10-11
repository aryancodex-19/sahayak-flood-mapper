import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { useLanguage } from "@/lib/language-context";
import type { DataBundle, DashboardStats, Language } from "@/types/data";

interface SituationReportProps {
  data: DataBundle;
  stats: DashboardStats;
  language: Language;
}

export function SituationReport({ data, stats, language }: SituationReportProps) {
  const { t } = useLanguage();
  const sorted = [...data.settlements].sort((a, b) => b.priorityScore - a.priorityScore).slice(0, 3);
  const date = new Date().toLocaleDateString(language === "hi" ? "hi-IN" : "en-IN");

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
    <Card id="report" className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <h2 className="font-display text-xl font-semibold">
          {t("situationReport")}
        </h2>
        <span className="text-xs text-muted-foreground">{date}</span>
      </div>

      <div className="space-y-4 text-sm leading-7">
        <div>
          <p className="text-muted-foreground">{t("regionLabel")}</p>
          <p className="font-medium">{t("region")}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div><p className="text-muted-foreground">{t("floodExtentStat")}</p><p className="font-medium">{stats.floodAreaHectares.toLocaleString()} {t("hectares")}</p></div>
          <div><p className="text-muted-foreground">{t("cutOffStat")}</p><p className="font-medium">{stats.cutOffCount}</p></div>
          <div><p className="text-muted-foreground">{t("affectedPop")}</p><p className="font-medium">{stats.affectedPopulation.toLocaleString()}</p></div>
        </div>
        <div>
          <p className="mb-2 text-muted-foreground">{t("top3Priority")}</p>
          <ol className="space-y-1.5">
            {sorted.map((s, i) => (
              <li key={s.id} className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                <span className="font-medium">{s.name}</span>
                <span className="text-muted-foreground">
                  {language === "hi"
                    ? `— आबादी: ${s.population.toLocaleString()} (प्राथमिकता: ${s.priorityScore.toFixed(2)})`
                    : `— Population: ${s.population.toLocaleString()} (Priority: ${s.priorityScore.toFixed(2)})`}
                </span>
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-md border border-warning/30 bg-warning/5 p-3">
          <p className="text-xs font-medium text-warning">{t("recommendedAction")}</p>
          <p className="mt-1 text-sm">{t("recommendedActionText")}</p>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        {t("numbersSourced")}
      </p>
    </Card>
    </motion.div>
  );
}