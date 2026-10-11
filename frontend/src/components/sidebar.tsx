import { motion } from "framer-motion";
import type { Language } from "@/types/data";
import { useLanguage } from "@/lib/language-context";
import { LayoutDashboard, Map as MapIcon, ListOrdered, FileText } from "lucide-react";

interface SidebarProps {
  language: Language;
  onLanguageChange: (lang: Language) => void;
  showFlood: boolean;
  onShowFloodChange: (v: boolean) => void;
  showSettlements: boolean;
  onShowSettlementsChange: (v: boolean) => void;
}

export function Sidebar({ language, onLanguageChange, showFlood, onShowFloodChange, showSettlements, onShowSettlementsChange }: SidebarProps) {
  const { t } = useLanguage();

  const navItems = [
    { icon: LayoutDashboard, label: t("navOverview"), target: "top" },
    { icon: MapIcon, label: t("navMap"), target: "map" },
    { icon: ListOrdered, label: t("navPriority"), target: "priority-table" },
    { icon: FileText, label: t("navReport"), target: "report" },
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
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t("menu")}
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
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{t("filters")}</h3>
          <div className="space-y-3">
            <div>
              <label className="mb-1.5 block text-xs text-muted-foreground">{t("regionLabel")}</label>
              <select className="w-full rounded-md border border-border bg-background/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                <option>{t("region")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs text-muted-foreground">{t("dateRange")}</label>
              <input type="date" className="w-full rounded-md border border-border bg-background/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
            </div>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{t("layers")}</h3>
          <div className="space-y-2">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={showFlood} onChange={(e) => onShowFloodChange(e.target.checked)} className="accent-primary" />
              {t("floodExtent")}
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" checked={showSettlements} onChange={(e) => onShowSettlementsChange(e.target.checked)} className="accent-primary" />
              {t("cutOffSettlements")}
            </label>
            <label className="flex cursor-not-allowed items-center gap-2 text-sm text-muted-foreground/50">
              <input type="checkbox" disabled className="accent-primary" />
              {t("roads")}
            </label>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{t("language")}</h3>
          <div className="flex gap-2">
            <motion.button
              onClick={() => onLanguageChange("en")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`flex-1 rounded-md border px-3 py-1.5 text-xs transition-colors ${language === "en" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"}`}
            >EN</motion.button>
            <motion.button
              onClick={() => onLanguageChange("hi")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`flex-1 rounded-md border px-3 py-1.5 text-xs transition-colors ${language === "hi" ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"}`}
            >HI</motion.button>
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{t("legend")}</h3>
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#38BDF8]" /><span className="text-muted-foreground">{t("floodExtent")}</span></div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#FF4757]" /><span className="text-muted-foreground">{t("cutOffSettlement")}</span></div>
            <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#2ED573]" /><span className="text-muted-foreground">{t("accessibleSettlement")}</span></div>
          </div>
        </div>
      </div>
    </aside>
  );
}