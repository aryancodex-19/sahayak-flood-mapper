import { motion } from "framer-motion";
import { Droplets, AlertTriangle, Users, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { DashboardStats } from "@/types/data";

interface StatsRowProps { stats: DashboardStats; }

export function StatsRow({ stats }: StatsRowProps) {
  const cards = [
    { label: "Flood Extent", value: `${stats.floodAreaHectares.toLocaleString()} hectares`, sub: "Total inundated area", icon: Droplets, tint: "bg-cyan-500/10 text-cyan-400" },
    { label: "Cut-off Settlements", value: stats.cutOffCount, sub: "Isolated communities", icon: AlertTriangle, tint: "bg-red-500/10 text-red-400" },
    { label: "Affected Population", value: stats.affectedPopulation.toLocaleString(), sub: "In cut-off zones", icon: Users, tint: "bg-amber-500/10 text-amber-400" },
    { label: "Avg Priority Score", value: stats.averagePriorityScore.toFixed(2), sub: "Across all settlements", icon: TrendingUp, tint: "bg-emerald-500/10 text-emerald-400" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4"
    >
      {cards.map(({ label, value, sub, icon: Icon, tint }) => (
        <Card key={label} className="p-6 transition-transform hover:-translate-y-0.5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
              <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
            </div>
            <div className={`rounded-lg p-2.5 ${tint}`}><Icon className="h-5 w-5" /></div>
          </div>
        </Card>
      ))}
    </motion.div>
  );
}