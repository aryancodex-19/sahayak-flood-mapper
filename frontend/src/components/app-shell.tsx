import type { ReactNode } from "react";
import type { Language, Scenario } from "@/types/data";
import { Navbar } from "./navbar";
import { Sidebar } from "./sidebar";

type Page = "overview" | "map" | "priority" | "report";

interface AppShellProps {
  children: ReactNode;
  scenario?: Scenario;
  onScenarioChange?: (s: Scenario) => void;
  language?: Language;
  onLanguageChange?: (lang: Language) => void;
  showFlood: boolean;
  onShowFloodChange: (v: boolean) => void;
  showSettlements: boolean;
  onShowSettlementsChange: (v: boolean) => void;
  onBackToHome: () => void;
  activePage: Page;
  onPageChange: (page: Page) => void;
}

export function AppShell({ children, ...sidebarProps }: AppShellProps) {
  const { onBackToHome, ...rest } = sidebarProps;
  return (
    <div className="min-h-screen bg-background">
      <Navbar onBackToHome={onBackToHome} />
      <div className="flex">
        <Sidebar {...rest} />
        <main className="flex-1 min-w-0 space-y-12 p-6">{children}</main>
      </div>
    </div>
  );
}