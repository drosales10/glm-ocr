import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import type { Block } from '../store/useOcrStore'

export function usePdfScrollToBlock(
	clickedBlockId: number | null,
	clickedBlock: Block | null,
	viewerRef: RefObject<HTMLDivElement>,
	pdfOriginalWidth: number,
	pdfOriginalHeight: number,
	resultStatus: string | undefined
) {
	const isScrollingRef = useRef(false)

	useEffect(() => {
		if (resultStatus !== 'completed' || !pdfOriginalWidth || !pdfOriginalHeight) return

		if (
			!clickedBlockId ||
			!clickedBlock ||
			!viewerRef.current ||
			!clickedBlock.bbox ||
			clickedBlock.bbox.length < 2
		)
			return

		// Marcar que se está haciendo scroll para evitar otras actualizaciones
		isScrollingRef.current = true

		const scrollToBlock = () => {
			// Buscar el contenedor de scroll del visor PDF (dentro de PdfViewer)
			const scrollContainer = viewerRef.current?.querySelector(
				'.pdf-scroll-container'
			) as HTMLElement

			if (!scrollContainer) {
				isScrollingRef.current = false
				return
			}

			const pageNumber = clickedBlock.pageIndex ?? 1

			// Intentar primero encontrar el elemento de la página
			let pageWrapper = viewerRef.current?.querySelector(
				`[data-pdf-page="${pageNumber}"]`
			) as HTMLElement | null
			let canvas = pageWrapper?.querySelector(
				'.react-pdf__Page__canvas'
			) as HTMLCanvasElement | null

			// Si la página aún no está renderizada, desplazarse primero a su posición aproximada
			if (!pageWrapper || !canvas) {
				// Intentar obtener la escala actual desde una página ya renderizada
				let currentScale = 1
				const visibleRenderedPage = viewerRef.current?.querySelector(
					'[data-pdf-visible]'
				) as HTMLElement | null
				const visibleCanvas = visibleRenderedPage?.querySelector(
					'.react-pdf__Page__canvas'
				) as HTMLCanvasElement | null

				if (visibleCanvas && visibleRenderedPage) {
					// Inferir la escala desde la primera página renderizada
					const displayHeight = visibleRenderedPage.getBoundingClientRect().height
					if (pdfOriginalHeight > 0) {
						currentScale = displayHeight / pdfOriginalHeight
					}
				}

				// Calcular la altura acumulada de la página destino (considerando la escala)
				let pageOffset = 20 // padding del contenedor
				for (let i = 1; i < pageNumber; i++) {
					const pageHeight = pdfOriginalHeight * currentScale
					pageOffset += pageHeight + 20 // altura de página + espaciado
				}

				// Desplazarse primero a la parte superior de la página
				scrollContainer.scrollTo({
					top: pageOffset,
					behavior: 'instant'
				})

				// Esperar a que la página se renderice y reintentar
				let retryCount = 0
				const maxRetries = 50 // Máximo 50 reintentos (aprox. 5 segundos)
				const checkAndScroll = () => {
					retryCount++
					if (retryCount > maxRetries) {
						isScrollingRef.current = false
						return
					}

					pageWrapper = viewerRef.current?.querySelector(
						`[data-pdf-page="${pageNumber}"]`
					) as HTMLElement | null
					canvas = pageWrapper?.querySelector(
						'.react-pdf__Page__canvas'
					) as HTMLCanvasElement | null

					if (!pageWrapper || !canvas) {
						// Si aún no está renderizada, seguir esperando
						requestAnimationFrame(checkAndScroll)
						return
					}

					// Página renderizada: realizar posicionamiento preciso
					performPreciseScroll(scrollContainer, pageWrapper, canvas)
				}

				// Retrasar un poco el inicio de la comprobación para dar tiempo al renderizado virtual
				setTimeout(() => {
					checkAndScroll()
				}, 100)
				return
			}

			// Página ya renderizada: realizar posicionamiento preciso directamente
			performPreciseScroll(scrollContainer, pageWrapper, canvas)
		}

		// Realizar posicionamiento preciso hasta el block
		const performPreciseScroll = (
			scrollContainer: HTMLElement,
			pageWrapper: HTMLElement,
			canvas: HTMLCanvasElement
		) => {
			// Obtener la posición del elemento de página dentro del contenedor de scroll
			const pageRect = pageWrapper.getBoundingClientRect()
			const containerRect = scrollContainer.getBoundingClientRect()

			// Calcular el desplazamiento de la página relativo al contenedor de scroll
			const pageOffsetY = pageRect.top - containerRect.top + scrollContainer.scrollTop

			const canvasRect = canvas.getBoundingClientRect()
			const scaleY = canvasRect.height / pdfOriginalHeight

			// bbox ahora son coordenadas relativas (dentro de cada página); usarlas directamente
			const yWithinPage = clickedBlock.bbox?.[1] ?? 0

			// Calcular posición destino: desplazamiento de página + coordenada y del bbox * escala
			const targetY = pageOffsetY + yWithinPage * scaleY - 100 // margen superior de 100px

			// Ejecutar el scroll
			scrollContainer.scrollTo({
				top: targetY,
				behavior: 'instant'
			})

			// Reiniciar la bandera tras completar el scroll
			setTimeout(() => {
				isScrollingRef.current = false
			}, 100) // breve retraso para asegurar que el scroll haya terminado
		}

		// Retrasar la ejecución para asegurar que la información de página esté actualizada
		const timer = setTimeout(scrollToBlock, 200)
		return () => {
			clearTimeout(timer)
			isScrollingRef.current = false
		}
	}, [clickedBlockId, clickedBlock, viewerRef, pdfOriginalHeight, pdfOriginalWidth, resultStatus])
}
