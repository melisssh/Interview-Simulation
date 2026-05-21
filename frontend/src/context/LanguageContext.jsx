import { createContext, useContext } from 'react'

const LanguageContext = createContext()

export function LanguageProvider({ children }) {
  const lang = 'en'
  const toggleLang = () => {}

  return (
    <LanguageContext.Provider value={{ lang, toggleLang }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}
