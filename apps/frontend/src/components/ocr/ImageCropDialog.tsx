import {
	useCallback,
	useEffect,
	useRef,
	useState,
	type PointerEvent as ReactPointerEvent
} from 'react'
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { cropImageFile, type CropRect } from '@/libs/cropImage'
import { cn } from '@/libs/utils'

type DragState = {
	startX: number
	startY: number
	currentX: number
	currentY: number
} | null

type DisplayRect = {
	left: number
	top: number
	width: number
	height: number
}

export type CropConfirmOptions = {
	/** Si es true, se envía el recorte y se deja abierta la misma imagen para otra zona. */
	continueOnSameFile: boolean
}

export interface ImageCropDialogProps {
	open: boolean
	file: File | null
	queueLabel?: string
	onConfirm: (cropped: File, options: CropConfirmOptions) => void
	onUseFull: (original: File) => void
	/** Cierra sin enviar más zonas (si ya hubo recortes, no es un omitir). */
	onDoneWithFile: () => void
	/** Omite el archivo actual sin enviarlo (solo si no hubo zonas). */
	onCancel: () => void
}

function normalizeRect(drag: NonNullable<DragState>): DisplayRect {
	const left = Math.min(drag.startX, drag.currentX)
	const top = Math.min(drag.startY, drag.currentY)
	const width = Math.abs(drag.currentX - drag.startX)
	const height = Math.abs(drag.currentY - drag.startY)
	return { left, top, width, height }
}

export function ImageCropDialog({
	open,
	file,
	queueLabel,
	onConfirm,
	onUseFull,
	onDoneWithFile,
	onCancel
}: ImageCropDialogProps) {
	const containerRef = useRef<HTMLDivElement>(null)
	const imgRef = useRef<HTMLImageElement>(null)
	const [objectUrl, setObjectUrl] = useState<string | null>(null)
	const [drag, setDrag] = useState<DragState>(null)
	const [selection, setSelection] = useState<DisplayRect | null>(null)
	const [sentRegions, setSentRegions] = useState<DisplayRect[]>([])
	const [regionCount, setRegionCount] = useState(0)
	const [busy, setBusy] = useState(false)

	useEffect(() => {
		if (!file || !open) {
			setObjectUrl(null)
			setSelection(null)
			setDrag(null)
			setSentRegions([])
			setRegionCount(0)
			return
		}
		const url = URL.createObjectURL(file)
		setObjectUrl(url)
		setSelection(null)
		setDrag(null)
		setSentRegions([])
		setRegionCount(0)
		return () => URL.revokeObjectURL(url)
	}, [file, open])

	const clientToLocal = useCallback((clientX: number, clientY: number) => {
		const el = containerRef.current
		if (!el) return { x: 0, y: 0 }
		const rect = el.getBoundingClientRect()
		return {
			x: Math.min(Math.max(clientX - rect.left, 0), rect.width),
			y: Math.min(Math.max(clientY - rect.top, 0), rect.height)
		}
	}, [])

	const onPointerDown = (e: ReactPointerEvent) => {
		if (busy) return
		;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
		const p = clientToLocal(e.clientX, e.clientY)
		setDrag({ startX: p.x, startY: p.y, currentX: p.x, currentY: p.y })
		setSelection(null)
	}

	const onPointerMove = (e: ReactPointerEvent) => {
		if (!drag || busy) return
		const p = clientToLocal(e.clientX, e.clientY)
		setDrag({ ...drag, currentX: p.x, currentY: p.y })
	}

	const onPointerUp = () => {
		if (!drag) return
		const rect = normalizeRect(drag)
		setDrag(null)
		if (rect.width < 8 || rect.height < 8) {
			setSelection(null)
			return
		}
		setSelection(rect)
	}

	const displayToNatural = (disp: DisplayRect): CropRect | null => {
		const img = imgRef.current
		const box = containerRef.current
		if (!img || !box || !img.naturalWidth || !img.naturalHeight) return null

		const boxRect = box.getBoundingClientRect()
		const imgRect = img.getBoundingClientRect()
		const offsetX = imgRect.left - boxRect.left
		const offsetY = imgRect.top - boxRect.top
		const scaleX = img.naturalWidth / imgRect.width
		const scaleY = img.naturalHeight / imgRect.height

		const x1 = (disp.left - offsetX) * scaleX
		const y1 = (disp.top - offsetY) * scaleY
		const x2 = (disp.left + disp.width - offsetX) * scaleX
		const y2 = (disp.top + disp.height - offsetY) * scaleY

		const left = Math.max(0, Math.min(x1, x2))
		const top = Math.max(0, Math.min(y1, y2))
		const right = Math.min(img.naturalWidth, Math.max(x1, x2))
		const bottom = Math.min(img.naturalHeight, Math.max(y1, y2))

		return {
			x: left,
			y: top,
			width: Math.max(1, right - left),
			height: Math.max(1, bottom - top)
		}
	}

	const handleConfirm = async (continueOnSameFile: boolean) => {
		if (!file || !selection) return
		const crop = displayToNatural(selection)
		if (!crop || crop.width < 4 || crop.height < 4) return
		setBusy(true)
		try {
			const nextIndex = regionCount + 1
			const cropped = await cropImageFile(file, crop, {
				nameSuffix: `_zona${nextIndex}`
			})
			onConfirm(cropped, { continueOnSameFile })
			if (continueOnSameFile) {
				setSentRegions(prev => [...prev, selection])
				setRegionCount(nextIndex)
				setSelection(null)
				setDrag(null)
			}
		} catch (err: unknown) {
			console.error(err)
			onUseFull(file)
		} finally {
			setBusy(false)
		}
	}

	const live = drag ? normalizeRect(drag) : selection
	const hasValidSelection = !!live && live.width >= 8 && live.height >= 8
	const nextZone = regionCount + 1

	return (
		<Dialog
			open={open}
			onOpenChange={next => {
				if (!next && !busy) {
					if (regionCount > 0) onDoneWithFile()
					else onCancel()
				}
			}}>
			<DialogContent
				showCloseButton={!busy}
				className='sm:max-w-3xl max-h-[90vh] overflow-hidden flex flex-col bg-white dark:bg-gray-950'>
				<DialogHeader>
					<DialogTitle>Seleccionar área para OCR</DialogTitle>
					<DialogDescription>
						Arrastra para marcar una zona. Puedes enviar varias partes de la misma página.
						{queueLabel ? ` ${queueLabel}` : ''}
						{regionCount > 0 ? ` · ${regionCount} zona${regionCount === 1 ? '' : 's'} enviada${regionCount === 1 ? '' : 's'}` : ''}
					</DialogDescription>
				</DialogHeader>

				<div
					ref={containerRef}
					className={cn(
						'relative w-full h-[min(58vh,520px)] rounded-md border border-border bg-gray-100 dark:bg-gray-900 overflow-hidden select-none touch-none',
						busy ? 'cursor-wait' : 'cursor-crosshair'
					)}
					onPointerDown={onPointerDown}
					onPointerMove={onPointerMove}
					onPointerUp={onPointerUp}
					onPointerCancel={onPointerUp}>
					{objectUrl && (
						<img
							ref={imgRef}
							src={objectUrl}
							alt='Vista previa para recorte'
							draggable={false}
							className='absolute inset-0 m-auto max-w-full max-h-full object-contain pointer-events-none'
						/>
					)}

					{/* Zonas ya enviadas (misma página) */}
					{sentRegions.map((r, i) => (
						<div
							key={`${r.left}-${r.top}-${i}`}
							className='absolute border border-dashed border-emerald-400/80 bg-emerald-400/15 pointer-events-none'
							style={{
								left: r.left,
								top: r.top,
								width: r.width,
								height: r.height
							}}>
							<span className='absolute left-0.5 top-0.5 rounded bg-emerald-600/90 text-[10px] text-white px-1 leading-4'>
								{i + 1}
							</span>
						</div>
					))}

					{/* Oscurece fuera del recorte actual */}
					{hasValidSelection && live && (
						<>
							<div
								className='absolute left-0 right-0 top-0 bg-black/45 pointer-events-none'
								style={{ height: live.top }}
							/>
							<div
								className='absolute left-0 bg-black/45 pointer-events-none'
								style={{
									top: live.top,
									height: live.height,
									width: live.left
								}}
							/>
							<div
								className='absolute right-0 bg-black/45 pointer-events-none'
								style={{
									top: live.top,
									height: live.height,
									left: live.left + live.width
								}}
							/>
							<div
								className='absolute left-0 right-0 bottom-0 bg-black/45 pointer-events-none'
								style={{ top: live.top + live.height }}
							/>
							<div
								className='absolute border-2 border-primary pointer-events-none'
								style={{
									left: live.left,
									top: live.top,
									width: live.width,
									height: live.height
								}}>
								<span className='absolute left-0.5 top-0.5 rounded bg-primary text-[10px] text-primary-foreground px-1 leading-4'>
									{nextZone}
								</span>
							</div>
						</>
					)}

					{!hasValidSelection && (
						<div className='absolute inset-x-0 bottom-3 flex justify-center pointer-events-none'>
							<span className='rounded-md bg-black/60 text-white text-xs px-2 py-1'>
								{regionCount > 0
									? 'Marca otra zona de la página'
									: 'Arrastra para seleccionar el área'}
							</span>
						</div>
					)}
				</div>

				<DialogFooter className='gap-2 sm:gap-2 flex-col sm:flex-row sm:flex-wrap sm:justify-end'>
					<Button
						type='button'
						variant='outline'
						disabled={busy}
						onClick={() => (regionCount > 0 ? onDoneWithFile() : onCancel())}>
						{regionCount > 0 ? 'Listo con este archivo' : 'Omitir archivo'}
					</Button>
					{regionCount === 0 && (
						<Button
							type='button'
							variant='secondary'
							disabled={busy || !file}
							onClick={() => file && onUseFull(file)}>
							Usar imagen completa
						</Button>
					)}
					<Button
						type='button'
						variant='secondary'
						disabled={busy || !selection}
						onClick={() => void handleConfirm(true)}>
						{busy ? 'Recortando…' : 'Usar y seguir recortando'}
					</Button>
					<Button
						type='button'
						disabled={busy || !selection}
						onClick={() => void handleConfirm(false)}>
						{busy ? 'Recortando…' : regionCount > 0 ? 'Usar y siguiente archivo' : 'Usar recorte'}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	)
}
