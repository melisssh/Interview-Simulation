export const API = import.meta.env.VITE_API_URL || '/api'

export function apiLangHeader() {
  const lang = localStorage.getItem('appLang') || 'tr'
  return { 'Accept-Language': lang }
}
