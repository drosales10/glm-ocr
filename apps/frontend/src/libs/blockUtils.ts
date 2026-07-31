import type { Block } from '../store/useOcrStore'

/**
 * Comprueba si un punto está dentro del bbox
 */
export function isPointInBbox(
	x: number,
	y: number,
	bbox: [number, number, number, number]
): boolean {
	const [x1, y1, x2, y2] = bbox
	return x >= x1 && x <= x2 && y >= y1 && y <= y2
}

/**
 * Busca el block que contiene las coordenadas dadas
 */
export function findBlockAtPoint(
	blocks: Block[],
	x: number,
	y: number,
	pageIndex?: number
): Block | undefined {
	return blocks.find(block => {
		if (!block.bbox) return false
		if (pageIndex !== undefined && block.pageIndex !== pageIndex) return false
		return isPointInBbox(x, y, block.bbox)
	})
}

/**
 * Conversión de coordenadas PDF: de coordenadas de pantalla a coordenadas relativas del PDF
 */
export function convertPdfScreenToRelative(
	screenX: number,
	screenY: number,
	canvasRect: DOMRect,
	pdfOriginalWidth: number,
	pdfOriginalHeight: number
): { x: number; y: number } {
	const scaleX = canvasRect.width / pdfOriginalWidth
	const scaleY = canvasRect.height / pdfOriginalHeight
	return {
		x: screenX / scaleX,
		y: screenY / scaleY
	}
}

/**
 * Conversión de coordenadas de imagen: de coordenadas de pantalla a coordenadas originales de la imagen
 */
export function convertImageScreenToOriginal(
	screenX: number,
	screenY: number,
	imgElement: HTMLImageElement
): { x: number; y: number } {
	const imgRect = imgElement.getBoundingClientRect()
	const imgNaturalWidth = imgElement.naturalWidth
	const imgNaturalHeight = imgElement.naturalHeight
	const imgDisplayWidth = imgRect.width
	const imgDisplayHeight = imgRect.height

	const scaleX = imgNaturalWidth / imgDisplayWidth
	const scaleY = imgNaturalHeight / imgDisplayHeight

	return {
		x: screenX * scaleX,
		y: screenY * scaleY
	}
}
