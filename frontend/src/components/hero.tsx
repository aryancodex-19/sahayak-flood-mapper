import { BurinHatch } from "@/components/ui/hero-burin-hatch";
import { useLanguage } from "@/lib/language-context";

interface HeroProps {
  onViewMap: () => void;
}

export function Hero({ onViewMap }: HeroProps) {
  const { t } = useLanguage();

  return (
    <BurinHatch
      eyebrow={t("heroBadge").toUpperCase()}
      headline={[t("heroTitle")]}
      subcopy={t("heroSubtitle")}
      primaryCta={{
        label: t("viewMap"),
        onClick: onViewMap,
      }}

      plateLabel={t("heroSubtitle")}
      className="min-h-screen w-full"
    />
  );
}

export default Hero;
