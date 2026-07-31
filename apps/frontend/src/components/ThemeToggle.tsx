import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { applyTheme, getResolvedTheme, toggleTheme, type Theme } from '@/libs/theme'

export function ThemeToggle() {
	const [theme, setThemeState] = useState<Theme>(() =>
		typeof document !== 'undefined' ? getResolvedTheme() : 'light'
	)

	useEffect(() => {
		applyTheme(theme)
	}, [theme])

	const handleToggle = () => {
		setThemeState(toggleTheme())
	}

	const isDark = theme === 'dark'

	return (
		<Button
			type='button'
			variant='outline'
			size='icon-sm'
			className='cursor-pointer shrink-0'
			onClick={handleToggle}
			aria-label={isDark ? 'Activar modo claro' : 'Activar modo oscuro'}
			title={isDark ? 'Modo claro' : 'Modo oscuro'}>
			{isDark ? <Sun className='size-4' /> : <Moon className='size-4' />}
		</Button>
	)
}
