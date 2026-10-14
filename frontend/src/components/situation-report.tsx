import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import type { DataBundle, DashboardStats, Language } from "@/types/data";

interface SituationReportProps {
  data: DataBundle;
  stats: DashboardStats;
  language?: Language;
}

export function SituationReport({ data, stats }: SituationReportProps) {
  const cutOffSettlements = data.settlements.filter((s) => s.status === "cut-off");
  const sorted = [...cutOffSettlements].sort((a, b) => b.priorityScore - a.priorityScore).slice(0, 3);
  const date = new Date().toLocaleDateString("en-IN");

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
            Flood Situation Report
          </h2>
          <span className="text-xs text-muted-foreground">{date}</span>
        </div>

        <div className="space-y-4 text-sm leading-7">
          <div>
            <p className="text-muted-foreground">Region</p>
            <p className="font-medium">Kamrup, Assam</p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div><p className="text-muted-foreground">Flood Extent</p><p className="font-medium">{stats.floodAreaHectares.toLocaleString()} hectares</p></div>
            <div><p className="text-muted-foreground">Cut-off Settlements</p><p className="font-medium">{stats.cutOffCount}</p></div>
            <div><p className="text-muted-foreground">Affected Population</p><p className="font-medium">{stats.affectedPopulation.toLocaleString()}</p></div>
          </div>
          <div>
            <p className="mb-2 text-muted-foreground">Top 3 Priority Areas</p>
            {sorted.length === 0 ? (
              <p className="text-sm italic text-muted-foreground">No cut-offs identified in this scenario</p>
            ) : (
              <ol className="space-y-1.5">
                {sorted.map((s, i) => (
                  <li key={s.id} className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{i + 1}.</span>
                    <span className="font-medium">{s.name}</span>
                    <span className="text-muted-foreground">
                      {`— Population: ${s.population.toLocaleString()} (Priority: ${s.priorityScore.toFixed(2)})`}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
          <div className="rounded-md border border-warning/30 bg-warning/5 p-3">
            <p className="text-xs font-medium text-warning">Recommended Action</p>
            <p className="mt-1 text-sm">
              {stats.cutOffCount === 0
                ? "No cut-offs identified in this scenario. All settlements have active access to service centers."
                : "Immediate air/boat rescue to the top priority settlements. Coordinate with district administration for road clearance."}
            </p>
          </div>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          Numbers sourced from flood map data. Not LLM-generated.
        </p>
      </Card>
    </motion.div>
  );
}