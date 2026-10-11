import { createContext, useContext } from "react";
import type { Language } from "@/types/data";
import { translations, type TranslationKey } from "./i18n";

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: TranslationKey) => string;
}

export const LanguageContext = createContext<LanguageContextValue | null>(null);

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (ctx) return ctx;
  return {
    language: "en" as Language,
    setLanguage: () => {},
    t: (key: TranslationKey) => translations.en[key] || "",
  };
}