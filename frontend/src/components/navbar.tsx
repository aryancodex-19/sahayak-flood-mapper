import { Waves } from "lucide-react";
import { useLanguage } from "@/lib/language-context";

interface NavbarProps {
  onBackToHome: () => void;
}

export function Navbar({ onBackToHome }: NavbarProps) {
  const { t } = useLanguage();
  return (
    <nav className="sticky top-0 z-50 h-16 border-b border-border bg-background/60 backdrop-blur-md">
      <div className="container mx-auto flex h-full items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <Waves style={{ width: 20, height: 20 }} className="text-primary" />
          <span className="font-display text-xl font-semibold tracking-tight">SAHAYAK</span>
        </div>
        <div className="hidden items-center gap-2 rounded-full border border-border bg-background/50 px-4 py-1.5 text-sm backdrop-blur-md md:flex">
          <span className="h-2 w-2 animate-pulse rounded-full bg-success" />
          <span className="text-muted-foreground">{t("region")}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-3 py-1 text-xs font-medium text-success">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
            {t("live")}
          </div>
          <button
            onClick={onBackToHome}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {t("home")}
          </button>
        </div>
      </div>
    </nav>
  );
}