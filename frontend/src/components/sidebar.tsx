import { motion } from "framer-motion";
import type { Language, Scenario } from "@/types/data";
import { LayoutDashboard, Map as MapIcon, ListOrdered, FileText } from "lucide-react";

interface SidebarProps {
  scenario?: Scenario;
  onScenarioChange?: (s: Scenario) => void;
  language?: Language;
  onLanguageChange?: (lang: Language) => void;
  showFlood: boolean;
  onShowFloodChange: (v: boolean) => void;
  showSettlements: boolean;
  onShowSettlementsChange: (v: boolean) => void;
}

export function Sidebar({ scenario = "severe", onScenarioChange, showFlood, onShowFloodChange, showSettlements, onShowSettlementsChange }: SidebarProps) {
  const navItems = [
    { icon: LayoutDashboard, label: "Overview", target: "top" },
    { icon: MapIcon, label: "Map", target: "map" },
    { icon: ListOrdered, label: "Priority List", target: "priority-table" },
    { icon: FileText, label: "Report", target: "report" },
  ];

  const handleNavClick = (target: string) => {
    if (target === "top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card/30 md:block">
      <div className="space-y-6 p-4">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Scenario</h3>
          <div className="flex rounded-lg border border-border bg-background/50 p-1">
            <button
              type="button"
              onClick={() => onScenarioChange?.("severe")}
              className={`flex-1 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                scenario === "severe"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Severe Scenario
            </button>
            <button
              type="button"
              onClick={() => onScenarioChange?.("real")}
              className={`flex-1 rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                scenario === "real"
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Real Event
            </button>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Menu
          </h3>
          <nav className="space-y-1">
            {navItems.map(({ icon: Icon, label, target }) => (
              <motion.button
                key={target}
                onClick={() => handleNavClick(target)}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/30 hover:text-foreground"
              >
                <Icon className="h-4 w-4" />
                {label}
              </motion.button>
            ))}
          </nav>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Filters</h3>
          <div className="space-y-3">
            <div>
              <label className="mb-1.5 block text-xs text-muted-foreground">Region</label>
              <select className="w-full rounded-md border border-border bg-background/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                <option>Kamrup, Assam</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-muted-foreground">Date Range</label>
              <input type="date" className="w-full rounded-md border border-border bg-background/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
            </div>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Layers</h3>
          <div className="space-y-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={showFlood} onChange={(e) => onShowFloodChange(e.target.checked)} className="accent-primary" />
              Flood Extent
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={showSettlements} onChange={(e) => onShowSettlementsChange(e.target.checked)} className="accent-primary" />
              Cut-off Settlements
            </label>
            <label className="flex cursor-not-allowed items-center gap-2 text-sm text-muted-foreground/50">
              <input type="checkbox" disabled className="accent-primary" />
              Roads (Coming soon)
            </label>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Legend</h3>
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#38BDF8]" /><span className="text-muted-foreground">Flood Extent</span></div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#FF4757]" /><span className="text-muted-foreground">Strict Cut-off</span></div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#F59E0B]" /><span className="text-muted-foreground">Practical Cut-off</span></div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#2ED573]" /><span className="text-muted-foreground">Accessible Settlement</span></div>
          </div>
        </div>
      </div>
    </aside>
  );
}