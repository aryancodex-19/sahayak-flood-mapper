import { motion } from "framer-motion";
import { Download } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import type { Settlement } from "@/types/data";

interface PriorityTableProps { settlements: Settlement[]; }

export function PriorityTable({ settlements }: PriorityTableProps) {
  // Filter for cut-off settlements (strict + practical) and sort descending by priority
  const cutOffs = settlements.filter((s) => s.status === "cut-off");
  const sorted = [...cutOffs].sort((a, b) => b.priorityScore - a.priorityScore);

  const handleDownload = () => {
    const header = "Rank,Settlement,Population,Priority,Status\n";
    const rows = sorted.map((s, i) => {
      const statusLabel =
        s.statusType === "strict-cutoff"
          ? "Strict Cut-off"
          : s.statusType === "practical-cutoff"
          ? "Practical Cut-off"
          : "Accessible";
      return `${i + 1},"${s.name}",${s.population},${s.priorityScore},${statusLabel}`;
    }).join("\n");
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
          <h2 className="font-display text-xl font-semibold">Rescue Priority List</h2>
          <p className="text-sm text-muted-foreground">{sorted.length} settlements ranked</p>
        </div>
        <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
          <Button variant="outline" size="sm" onClick={handleDownload} disabled={sorted.length === 0}>
            <Download className="mr-2 h-4 w-4" /> Download CSV
          </Button>
        </motion.div>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">Rank</TableHead>
            <TableHead>Settlement</TableHead>
            <TableHead>Population</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                No cut-off settlements — all settlements accessible
              </TableCell>
            </TableRow>
          ) : (
            sorted.map((s, idx) => (
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
                  {s.statusType === "strict-cutoff" && (
                    <Badge variant="red" className="border-red-500/20 bg-red-500/10 text-red-400">
                      Strict Cut-off
                    </Badge>
                  )}
                  {s.statusType === "practical-cutoff" && (
                    <Badge variant="amber" className="border-amber-500/20 bg-amber-500/10 text-amber-400">
                      Practical Cut-off
                    </Badge>
                  )}
                  {(!s.statusType || s.statusType === "connected") && (
                    <Badge variant="green" className="border-emerald-500/20 bg-emerald-500/10 text-emerald-400">
                      Accessible
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <p className="mt-4 text-xs text-muted-foreground">Ranked by priority score. Numbers sourced from flood analysis data.</p>
    </Card>
    </motion.div>
  );
}