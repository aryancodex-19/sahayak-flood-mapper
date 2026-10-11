import { motion } from "framer-motion";
import { Download } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { useLanguage } from "@/lib/language-context";
import type { Settlement } from "@/types/data";

interface PriorityTableProps { settlements: Settlement[]; }

export function PriorityTable({ settlements }: PriorityTableProps) {
  const { t } = useLanguage();
  // Filter for cut-off settlements (strict + practical) and sort descending by priority
  const cutOffs = settlements.filter((s) => s.status === "cut-off");
  const sorted = [...(cutOffs.length > 0 ? cutOffs : settlements)].sort(
    (a, b) => b.priorityScore - a.priorityScore
  );

  const handleDownload = () => {
    const header = "Rank,Settlement,Population,Priority,Status\n";
    const rows = sorted.map((s, i) => `${i + 1},"${s.name}",${s.population},${s.priorityScore},${s.status}`).join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sahayak-priority-list.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
    <Card id="priority-table" className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-semibold">{t("rescuePriorityList")}</h2>
          <p className="text-sm text-muted-foreground">{sorted.length} settlements ranked</p>
        </div>
        <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" /> {t("downloadCSV")}
          </Button>
        </motion.div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">{t("rank")}</TableHead>
            <TableHead>{t("settlement")}</TableHead>
            <TableHead>{t("population")}</TableHead>
            <TableHead>{t("priority")}</TableHead>
            <TableHead>{t("status")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((s, idx) => (
            <TableRow key={s.id}>
              <TableCell className="font-medium text-muted-foreground">#{idx + 1}</TableCell>
              <TableCell className="font-medium">{s.name}</TableCell>
              <TableCell>{s.population.toLocaleString()}</TableCell>
              <TableCell>
                <div className="flex items-center gap-3">
                  <Progress value={s.priorityScore > 1 ? s.priorityScore : s.priorityScore * 100} className="h-2 w-24" />
                  <span className="text-xs text-muted-foreground">{s.priorityScore.toFixed(2)}</span>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={s.status === "cut-off" ? "destructive" : "secondary"}>
                  {s.status === "cut-off" ? t("cutOff") : t("accessible")}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-4 text-xs text-muted-foreground">{t("rankedBy")}</p>
    </Card>
    </motion.div>
  );
}