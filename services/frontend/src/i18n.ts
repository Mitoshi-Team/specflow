import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import ru from "./locales/ru.json";

const STORAGE_KEY_LANG = "lang";

function getInitialLanguage(): string {
  if (typeof window === "undefined") {
    return "ru";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY_LANG);
  if (stored === "ru" || stored === "en") {
    return stored;
  }

  return "ru";
}

void i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: getInitialLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

function syncHtmlLang(language: string) {
  if (typeof document !== "undefined") {
    document.documentElement.lang = language;
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY_LANG, language);
  }
}

syncHtmlLang(i18n.language);

i18n.on("languageChanged", (language) => {
  syncHtmlLang(language);
});

export default i18n;
export { STORAGE_KEY_LANG, getInitialLanguage };
