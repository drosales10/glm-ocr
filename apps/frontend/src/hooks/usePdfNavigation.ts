import { useState, useCallback, useEffect, useRef } from 'react'

interface UsePdfNavigationOptions {
	numPages: number
	getPageOffset: (pageNumber: number) => number
	scrollContainerRef: React.RefObject<HTMLDivElement | null>
	onPageChange?: (page: number) => void
}

export function usePdfNavigation({
	numPages,
	getPageOffset,
	scrollContainerRef,
	onPageChange
}: UsePdfNavigationOptions) {
	const [currentPage, setCurrentPage] = useState<number>(1)
	const [inputValue, setInputValue] = useState<string>('1')
	const isProgrammaticScrollRef = useRef<boolean>(false)
	const lastProgrammaticPageRef = useRef<number>(0)

	// Ir a una página concreta
	const goToPage = useCallback(
		(page: number) => {
			const target = Math.max(1, Math.min(page, numPages))

			// Marcar como scroll programático y registrar la página destino
			isProgrammaticScrollRef.current = true
			lastProgrammaticPageRef.current = target

			setCurrentPage(target)
			setInputValue(target.toString())
			onPageChange?.(target)

			// Calcular la posición de scroll de la página destino
			const offset = getPageOffset(target)
			const container = scrollContainerRef.current
			if (container) {
				container.scrollTo({
					top: offset,
					behavior: 'instant'
				})

				// Retrasar el reinicio de la marca para asegurar que el evento de scroll se procese
				setTimeout(() => {
					isProgrammaticScrollRef.current = false
				}, 100)
			}
		},
		[numPages, getPageOffset, scrollContainerRef, onPageChange]
	)

	// Debounce del cambio en el input
	useEffect(() => {
		const timer = setTimeout(() => {
			const val = parseInt(inputValue)
			if (!isNaN(val) && val >= 1 && val <= numPages && val !== currentPage) {
				goToPage(val)
			} else if (isNaN(val) || val < 1 || val > numPages) {
				// Si la entrada no es válida, restaurar el número de página actual
				setInputValue(currentPage.toString())
			}
		}, 500) // Retraso de debounce de 500ms

		return () => clearTimeout(timer)
	}, [inputValue, numPages, currentPage, goToPage])

	// Página anterior / siguiente
	const prevPage = useCallback(() => goToPage(currentPage - 1), [currentPage, goToPage])
	const nextPage = useCallback(() => goToPage(currentPage + 1), [currentPage, goToPage])

	// Reiniciar el número de página
	const resetPage = useCallback(() => {
		setCurrentPage(1)
		setInputValue('1')
	}, [])

	return {
		currentPage,
		inputValue,
		setInputValue,
		setCurrentPage,
		goToPage,
		prevPage,
		nextPage,
		resetPage,
		isProgrammaticScrollRef,
		lastProgrammaticPageRef
	}
}
