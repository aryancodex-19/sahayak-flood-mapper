import { motion } from "framer-motion";
import type { Language, Scenario } from "@/types/data";
import { LayoutDashboard, Map as MapIcon, ListOrdered, FileText } from "lucide-react";
import { useLanguage } from "@/lib/language-context";

type Page = "overview" | "map" | "priority" | "report";

interface SidebarProps {
  scenario?: Scenario;
  onScenarioChange?: (s: Scenario) => void;
  language?: Language;
  onLanguageChange?: (lang: Language) => void;
  showFlood: boolean;
  onShowFloodChange: (v: boolean) => void;
  showSettlements: boolean;
  onShowSettlementsChange: (v: boolean) => void;
  activePage: Page;
  onPageChange: (page: Page) => void;
}

export function Sidebar({ scenario = "severe", onScenarioChange, showFlood, onShowFloodChange, showSettlements, onShowSettlementsChange, activePage, onPageChange }: SidebarProps) {
const { t } = useLanguage();
  const navItems: { icon: React.ComponentType<{ className?: string }>; label: string; page: Page }[] = [
    { icon: LayoutDashboard, label: t("navOverview"), page: "overview" },
    { icon: MapIcon, label: t("navMap"), page: "map" },
    { icon: ListOrdered, label: t("navPriority"), page: "priority" },
    { icon: FileText, label: t("navReport"), page: "report" },
  ];

  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card/30 md:block">
      <div className="space-y-6 p-4">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Scenario</h3>
          <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-background/50 p-1.5">
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => onScenarioChange?.("severe")}
                className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
                  scenario === "severe"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                }`}
              >
                Severe
              </button>
              <button
                type="button"
                onClick={() => onScenarioChange?.("real")}
                className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
                  scenario === "real"
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                }`}
              >
                Real Event
              </button>
            </div>
            <button
              type="button"
              onClick={() => onScenarioChange?.("ml")}
              className={`w-full rounded px-2.5 py-1.5 text-xs font-medium transition-colors flex items-center justify-between border ${
                scenario === "ml"
                  ? "bg-purple-600 text-white border-purple-500 shadow-sm font-semibold"
                  : "border-purple-500/30 text-purple-300/90 hover:text-purple-200 hover:bg-purple-500/10"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <span className={`h-1.5 w-1.5 rounded-full ${scenario === "ml" ? "bg-white" : "bg-purple-400"}`} />
                Experimental ML (U-Net)
              </span>
              <span className={`text-[9px] px-1 py-0.5 rounded uppercase font-mono font-bold ${
                scenario === "ml" ? "bg-purple-800 text-purple-100" : "bg-purple-500/20 text-purple-300"
              }`}>
                AI
              </span>
            </button>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Menu
          </h3>
          <nav className="space-y-1">
            {navItems.map(({ icon: Icon, label, page }) => (
              <motion.button
                key={page}
                onClick={() => onPageChange(page)}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                className={`flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                  activePage === page
                    ? "bg-primary/10 text-primary border-l-2 border-primary"
                    : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
                }`}
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

