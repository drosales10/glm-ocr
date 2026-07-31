const STORAGE_KEY = 'glm-ocr-theme'
export const THEME_EVENT = 'glm-ocr-theme'

export type Theme = 'light' | 'dark'

export function getStoredTheme(): Theme | null {
	try {
		const value = localStorage.getItem(STORAGE_KEY)
		if (value === 'light' || value === 'dark') return value
	} catch {
		/* ignore */
	}
	return null
}

export function getSystemTheme(): Theme {
	if (typeof window === 'undefined') return 'light'
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function getResolvedTheme(): Theme {
	return getStoredTheme() ?? getSystemTheme()
}

export function applyTheme(theme: Theme) {
	const root = document.documentElement
	root.classList.toggle('dark', theme === 'dark')
	root.style.colorScheme = theme
	root.dataset.theme = theme
}

export function setTheme(theme: Theme) {
	try {
		localStorage.setItem(STORAGE_KEY, theme)
	} catch {
		/* ignore */
	}
	applyTheme(theme)
	window.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: theme }))
}

export function toggleTheme(): Theme {
	const next: Theme = getResolvedTheme() === 'dark' ? 'light' : 'dark'
	setTheme(next)
	return next
}
