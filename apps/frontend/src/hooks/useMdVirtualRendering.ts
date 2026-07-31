import { useState, useRef, useEffect, useCallback, useLayoutEffect } from 'react'

interface MdVirtualRenderingConfig {
	bufferSize: number // tamaño del búfer
	defaultItemHeight: number // altura predeterminada del elemento
	itemGap?: number // espacio entre elementos
	startIndex?: number // índice de inicio (PDF empieza en 1; blocks empiezan en 0)
}

interface UseMdVirtualRenderingOptions {
	containerRef: React.RefObject<HTMLElement | null>
	totalItems: number
	config: MdVirtualRenderingConfig
	scale?: number // factor de escala opcional (usado por PDF)
	onItemRender?: (index: number, element: HTMLElement) => void // callback al completar el renderizado de un elemento
}

export function useMdVirtualRendering({
	containerRef,
	totalItems,
	config,
	scale = 1,
	onItemRender
}: UseMdVirtualRenderingOptions) {
	const { bufferSize, defaultItemHeight, itemGap = 0, startIndex = 0 } = config

	const [visibleRange, setVisibleRange] = useState<[number, number]>([
		startIndex,
		startIndex
	])
	const [itemHeights, setItemHeights] = useState<Record<number, number>>({})
	const [totalHeight, setTotalHeight] = useState<number>(0)
	const [viewportHeight, setViewportHeight] = useState<number>(0)
	const resizeObserverRef = useRef<ResizeObserver | null>(null)

	// Calcular el desplazamiento acumulado de un elemento
	const getItemOffset = useCallback(
		(itemIndex: number): number => {
			let offset = 0
			const actualIndex = itemIndex - startIndex
			for (let i = 0; i < actualIndex; i++) {
				const index = i + startIndex
				const height = itemHeights[index] || defaultItemHeight
				offset += height * scale + itemGap
			}
			return offset
		},
		[itemHeights, defaultItemHeight, itemGap, scale, startIndex]
	)

	// Calcular la altura total
	useLayoutEffect(() => {
		if (totalItems === 0) {
			setTotalHeight(0)
			return
		}
		let height = 0
		for (let i = 0; i < totalItems; i++) {
			const index = i + startIndex
			const itemHeight = itemHeights[index] || defaultItemHeight
			height += itemHeight * scale
		}
		// Añadir el espacio entre elementos
		if (totalItems > 0) {
			height += (totalItems - 1) * itemGap
		}
		setTotalHeight(height)
	}, [totalItems, itemHeights, defaultItemHeight, itemGap, scale, startIndex])

	// Calcular el rango visible según la posición de scroll
	const calculateVisibleRange = useCallback(() => {
		if (!containerRef.current || viewportHeight === 0 || totalItems === 0) {
			return [startIndex, startIndex] as [number, number]
		}

		const scrollTop = containerRef.current.scrollTop

		// Encontrar el primer elemento parcialmente visible
		let startIdx = startIndex
		for (let i = 0; i < totalItems; i++) {
			const index = i + startIndex
			const itemOffset = getItemOffset(index)
			const itemHeight = (itemHeights[index] || defaultItemHeight) * scale
			const itemBottom = itemOffset + itemHeight

			if (itemBottom > scrollTop) {
				startIdx = index
				break
			}
		}

		// Encontrar el último elemento parcialmente visible
		const viewportBottom = scrollTop + viewportHeight
		let endIdx = startIndex + totalItems - 1
		for (let i = startIdx - startIndex; i < totalItems; i++) {
			const index = i + startIndex
			const itemOffset = getItemOffset(index)
			const itemHeight = (itemHeights[index] || defaultItemHeight) * scale
			if (itemOffset + itemHeight >= viewportBottom) {
				endIdx = index
				break
			}
		}

		// Añadir búfer
		startIdx = Math.max(startIndex, startIdx - bufferSize)
		endIdx = Math.min(startIndex + totalItems - 1, endIdx + bufferSize)

		return [startIdx, endIdx] as [number, number]
	}, [
		viewportHeight,
		totalItems,
		itemHeights,
		defaultItemHeight,
		itemGap,
		scale,
		getItemOffset,
		bufferSize,
		startIndex,
		containerRef
	])

	// Actualizar el rango visible
	const updateVisibleRange = useCallback(() => {
		const [start, end] = calculateVisibleRange()
		setVisibleRange([start, end])
	}, [calculateVisibleRange])

	// Escuchar el scroll
	useEffect(() => {
		const container = containerRef.current
		if (!container) return

		const handleScroll = () => {
			updateVisibleRange()
		}

		container.addEventListener('scroll', handleScroll)
		return () => container.removeEventListener('scroll', handleScroll)
	}, [updateVisibleRange, containerRef])

	// Escuchar cambios de tamaño del contenedor
	useEffect(() => {
		const container = containerRef.current
		if (!container) return

		const updateHeight = () => {
			setViewportHeight(container.clientHeight)
			updateVisibleRange()
		}

		updateHeight()

		resizeObserverRef.current = new ResizeObserver(() => {
			updateHeight()
		})
		resizeObserverRef.current.observe(container)

		return () => {
			resizeObserverRef.current?.disconnect()
			resizeObserverRef.current = null
		}
	}, [updateVisibleRange, containerRef])

	// Escuchar cambios de escala y actualizar el rango visible
	useEffect(() => {
		updateVisibleRange()
	}, [scale, updateVisibleRange])

	// Actualizar la altura de un elemento
	const updateItemHeight = useCallback(
		(itemIndex: number, height: number) => {
			// Si se usa escala, almacenar la altura original
			const originalHeight = scale !== 1 ? height / scale : height
			setItemHeights(prev => {
				if (prev[itemIndex] !== originalHeight) {
					return { ...prev, [itemIndex]: originalHeight }
				}
				return prev
			})
		},
		[scale]
	)

	// Manejar el renderizado exitoso de un elemento
	const handleItemRenderSuccess = useCallback(
		(itemIndex: number, element: HTMLElement) => {
			const renderedHeight = element.offsetHeight
			updateItemHeight(itemIndex, renderedHeight)
			onItemRender?.(itemIndex, element)
		},
		[updateItemHeight, onItemRender]
	)

	// Actualizar el rango visible en la inicialización
	useEffect(() => {
		updateVisibleRange()
	}, [totalItems, updateVisibleRange])

	return {
		visibleRange,
		itemHeights,
		totalHeight,
		viewportHeight,
		getItemOffset,
		handleItemRenderSuccess,
		updateVisibleRange
	}
}
