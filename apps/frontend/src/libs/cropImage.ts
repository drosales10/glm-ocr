export type CropRect = {
	x: number
	y: number
	width: number
	height: number
}

/** Carga un File de imagen en un HTMLImageElement. */
export function loadImageFromFile(file: File): Promise<HTMLImageElement> {
	return new Promise((resolve, reject) => {
		const url = URL.createObjectURL(file)
		const img = new Image()
		img.onload = () => {
			URL.revokeObjectURL(url)
			resolve(img)
		}
		img.onerror = () => {
			URL.revokeObjectURL(url)
			reject(new Error('No se pudo cargar la imagen'))
		}
		img.src = url
	})
}

/**
 * Recorta `file` al rectángulo en coordenadas de la imagen natural
 * y devuelve un nuevo File listo para subir al OCR.
 */
export async function cropImageFile(
	file: File,
	crop: CropRect,
	options?: { mimeType?: string; quality?: number; nameSuffix?: string }
): Promise<File> {
	const img = await loadImageFromFile(file)
	const x = Math.max(0, Math.round(crop.x))
	const y = Math.max(0, Math.round(crop.y))
	const width = Math.max(1, Math.min(Math.round(crop.width), img.naturalWidth - x))
	const height = Math.max(1, Math.min(Math.round(crop.height), img.naturalHeight - y))

	const canvas = document.createElement('canvas')
	canvas.width = width
	canvas.height = height
	const ctx = canvas.getContext('2d')
	if (!ctx) throw new Error('Canvas no disponible')

	ctx.drawImage(img, x, y, width, height, 0, 0, width, height)

	const preferPng = file.type === 'image/png' || file.name.toLowerCase().endsWith('.png')
	const mimeType = options?.mimeType || (preferPng ? 'image/png' : 'image/jpeg')
	const quality = options?.quality ?? 0.92

	const blob = await new Promise<Blob>((resolve, reject) => {
		canvas.toBlob(
			b => (b ? resolve(b) : reject(new Error('No se pudo generar el recorte'))),
			mimeType,
			quality
		)
	})

	const base = file.name.replace(/\.[^.]+$/, '') || 'crop'
	const suffix = options?.nameSuffix ?? '_crop'
	const ext = mimeType === 'image/png' ? 'png' : 'jpg'
	return new File([blob], `${base}${suffix}.${ext}`, {
		type: mimeType,
		lastModified: Date.now()
	})
}

export function isImageFile(file: File): boolean {
	return (
		file.type.startsWith('image/') ||
		/\.(png|jpe?g|webp|bmp|gif)$/i.test(file.name)
	)
}
