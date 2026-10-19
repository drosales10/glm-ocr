import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import {
	CheckCircle2,
	Crop,
	FileText,
	FolderOpen,
	Loader2,
	Square,
	Upload,
	XCircle
} from 'lucide-react'
import { cn, formatDuration, getOcrDurationSeconds, parseUtcMs } from '@/libs/utils'
import {
	cancelTask,
	formatStep,
	getTaskStatus,
	uploadTask,
	type OcrProfile,
	type TaskStatusData,
	type TaskStatus
} from '@/libs/api'
import { isImageFile } from '@/libs/cropImage'
import { toast } from 'sonner'
import { ThemeToggle } from '@/components/ThemeToggle'
import { ImageCropDialog } from '@/components/ocr/ImageCropDialog'

const OCR_PROFILE_KEY = 'glm-ocr-profile'
const OCR_CROP_KEY = 'glm-ocr-crop-before'

const OCR_PROFILES: Array<{ id: OcrProfile; label: string; hint: string }> = [
	{ id: 'fast', label: 'Rápido', hint: 'Páginas normales' },
	{ id: 'balanced', label: 'Equilibrado', hint: 'Recomendado' },
	{ id: 'math', label: 'Math', hint: 'Fórmulas / integrales' }
]

function readStoredProfile(): OcrProfile {
	try {
		const value = localStorage.getItem(OCR_PROFILE_KEY)
		if (value === 'fast' || value === 'balanced' || value === 'math') return value
	} catch {
		/* ignore */
	}
	return 'balanced'
}

function readStoredCropEnabled(): boolean {
	try {
		const value = localStorage.getItem(OCR_CROP_KEY)
		if (value === '0') return false
		if (value === '1') return true
	} catch {
		/* ignore */
	}
	return true
}

export type Layout = {
	block_content: string
	bbox: [number, number, number, number] | null
	block_id: number
	text_length?: number | null
}

export interface UploadedFile {
	id: string
	name: string
	size: number
	type: string
	file: File
	uploadTime: Date
	error: string | null
	/** Imagen original si este ítem es un recorte (para volver a marcar otra zona). */
	sourceOriginal?: File | null
}

export interface TaskResponse {
	fileId: string
	status: TaskStatus
	response: TaskStatusData | null
	error_message?: string | null
}

type QueueStatus = 'queued' | 'uploading' | TaskStatus

interface QueueItem {
	file: UploadedFile
	status: QueueStatus
	error?: string | null
	progress?: number
	currentStep?: string | null
	executionSeconds?: number | null
	/** epoch ms del started_at/created_at del backend (para cronómetro en vivo) */
	startedAtMs?: number | null
	taskId?: string | null
	stopping?: boolean
}

const STOPPABLE: ReadonlySet<QueueStatus> = new Set([
	'queued',
	'uploading',
	'pending',
	'processing'
])

interface FileUploadProps {
	onFileUploaded: (params: UploadedFile) => void
	onTaskStatusChange?: (params: TaskResponse) => void
}

const ALLOWED_FILE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf']
const ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf']
const MAX_FILE_SIZE = 20 * 1024 * 1024

const MAX_CONCURRENT_FILES = 3

const isValidFileType = (file: File): boolean =>
	ALLOWED_FILE_TYPES.includes(file.type) ||
	ALLOWED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext))

const formatFileSize = (bytes: number): string => {
	if (bytes < 1024) return `${bytes} B`
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
	return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const createFileId = (file: File) =>
	`${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`

const statusLabel: Record<QueueStatus, string> = {
	queued: 'En cola',
	uploading: 'Subiendo',
	pending: 'Pendiente',
	processing: 'Procesando',
	completed: 'Completado',
	failed: 'Fallido',
	cancelled: 'Cancelado'
}

export function FileUpload({ onFileUploaded, onTaskStatusChange }: FileUploadProps) {
	const [queue, setQueue] = useState<QueueItem[]>([])
	const [isDragging, setIsDragging] = useState(false)
	const [activeBatches, setActiveBatches] = useState(0)
	const [ocrProfile, setOcrProfile] = useState<OcrProfile>(() => readStoredProfile())
	const [cropEnabled, setCropEnabled] = useState(() => readStoredCropEnabled())
	const [cropQueue, setCropQueue] = useState<File[]>([])
	/** Total de imágenes del lote de recorte actual (para etiqueta “1 de N”). */
	const [cropBatchTotal, setCropBatchTotal] = useState(0)
	const [nowMs, setNowMs] = useState(() => Date.now())
	const fileInputRef = useRef<HTMLInputElement>(null)
	const directoryInputRef = useRef<HTMLInputElement>(null)
	const mountedRef = useRef(true)
	const ocrProfileRef = useRef(ocrProfile)
	/** IDs locales cuya cancelación el usuario pidió (corta polling/subida al instante). */
	const cancelledIdsRef = useRef(new Set<string>())
	const taskIdsRef = useRef(new Map<string, string>())
	const uploadAbortRef = useRef(new Map<string, AbortController>())

	const isLoading = activeBatches > 0 || cropQueue.length > 0
	const cropFile = cropQueue[0] ?? null
	const cropOpen = cropQueue.length > 0
	const cropDoneCount = cropBatchTotal > 0 ? cropBatchTotal - cropQueue.length : 0

	useEffect(() => {
		mountedRef.current = true
		return () => {
			mountedRef.current = false
			for (const controller of uploadAbortRef.current.values()) {
				controller.abort()
			}
			uploadAbortRef.current.clear()
		}
	}, [])

	useEffect(() => {
		ocrProfileRef.current = ocrProfile
		try {
			localStorage.setItem(OCR_PROFILE_KEY, ocrProfile)
		} catch {
			/* ignore */
		}
	}, [ocrProfile])

	useEffect(() => {
		try {
			localStorage.setItem(OCR_CROP_KEY, cropEnabled ? '1' : '0')
		} catch {
			/* ignore */
		}
	}, [cropEnabled])

	const hasBusyItems = useMemo(
		() =>
			queue.some(
				item =>
					item.status === 'queued' ||
					item.status === 'uploading' ||
					item.status === 'pending' ||
					item.status === 'processing'
			),
		[queue]
	)

	useEffect(() => {
		if (!hasBusyItems) return
		const id = window.setInterval(() => setNowMs(Date.now()), 1000)
		return () => window.clearInterval(id)
	}, [hasBusyItems])

	const completedCount = useMemo(
		() => queue.filter(item => item.status === 'completed').length,
		[queue]
	)
	const failedCount = useMemo(
		() => queue.filter(item => item.status === 'failed').length,
		[queue]
	)
	const cancelledCount = useMemo(
		() => queue.filter(item => item.status === 'cancelled').length,
		[queue]
	)
	const finishedCount = completedCount + failedCount + cancelledCount
	const progress = queue.length === 0 ? 0 : (finishedCount / queue.length) * 100

	const updateQueueItem = (
		fileId: string,
		status: QueueStatus,
		error?: string | null,
		progress?: number,
		currentStep?: string | null,
		executionSeconds?: number | null,
		startedAtMs?: number | null,
		extra?: Partial<Pick<QueueItem, 'taskId' | 'stopping'>>
	) => {
		if (!mountedRef.current) return
		setQueue(items =>
			items.map(item =>
				item.file.id === fileId
					? {
							...item,
							status,
							error: error ?? item.error,
							progress: progress ?? item.progress,
							currentStep: currentStep ?? item.currentStep,
							executionSeconds:
								executionSeconds !== undefined ? executionSeconds : item.executionSeconds,
							startedAtMs: startedAtMs !== undefined ? startedAtMs : item.startedAtMs,
							...extra
						}
					: item
			)
		)
	}

	const liveSecondsFor = (item: QueueItem): number | null => {
		if (item.status === 'completed' || item.status === 'failed' || item.status === 'cancelled') {
			return item.executionSeconds ?? null
		}
		if (
			item.status === 'processing' ||
			item.status === 'pending' ||
			item.status === 'uploading'
		) {
			if (item.startedAtMs != null) {
				return Math.max(0, (nowMs - item.startedAtMs) / 1000)
			}
			return item.executionSeconds ?? null
		}
		return null
	}

	const markCancelled = (fileId: string, message = 'Cancelado por el usuario') => {
		updateQueueItem(fileId, 'cancelled', message, undefined, null, undefined, undefined, {
			stopping: false
		})
		onTaskStatusChange?.({
			fileId,
			status: 'cancelled',
			response: null,
			error_message: message
		})
	}

	const stopQueueItem = (fileId: string) => {
		if (cancelledIdsRef.current.has(fileId)) return
		cancelledIdsRef.current.add(fileId)

		uploadAbortRef.current.get(fileId)?.abort()
		uploadAbortRef.current.delete(fileId)

		const taskId = taskIdsRef.current.get(fileId)
		updateQueueItem(fileId, 'cancelled', 'Cancelado por el usuario', undefined, null, undefined, undefined, {
			stopping: !!taskId
		})
		onTaskStatusChange?.({
			fileId,
			status: 'cancelled',
			response: null,
			error_message: 'Cancelado por el usuario'
		})

		if (!taskId) {
			toast.message('Proceso detenido')
			return
		}

		// Cancelación en servidor en segundo plano: no bloquea la UI
		void cancelTask(taskId)
			.then(() => {
				if (mountedRef.current) {
					updateQueueItem(
						fileId,
						'cancelled',
						'Cancelado por el usuario',
						undefined,
						null,
						undefined,
						undefined,
						{ stopping: false }
					)
				}
				toast.message('Proceso detenido')
			})
			.catch(() => {
				// Aunque el backend no cancele (p. ej. ya terminó), la UI ya dejó de esperar
				if (mountedRef.current) {
					updateQueueItem(
						fileId,
						'cancelled',
						'Detenido en la interfaz',
						undefined,
						null,
						undefined,
						undefined,
						{ stopping: false }
					)
				}
				toast.message('Detenido en la interfaz')
			})
	}

	const pollTask = async (fileId: string, taskId: string | number) => {
		let consecutiveErrors = 0
		while (mountedRef.current) {
			if (cancelledIdsRef.current.has(fileId)) return

			try {
				let response = await getTaskStatus(taskId)
				if (cancelledIdsRef.current.has(fileId)) return
				consecutiveErrors = 0

				// Evitar carrera: a veces status=completed llega antes de merged.json
				if (
					response.status === 'completed' &&
					!response.full_markdown &&
					!(response.layout && response.layout.length)
				) {
					await new Promise(resolve => setTimeout(resolve, 800))
					if (cancelledIdsRef.current.has(fileId)) return
					response = await getTaskStatus(taskId)
					if (cancelledIdsRef.current.has(fileId)) return
				}

				if (response.status === 'cancelled') {
					markCancelled(fileId)
					return
				}

				const step = formatStep(response.current_step ?? response.current_stage ?? null)
				const startedAtMs = parseUtcMs(response.started_at || response.created_at)
				const duration = getOcrDurationSeconds(response)
				updateQueueItem(
					fileId,
					response.status,
					null,
					response.progress,
					step,
					duration,
					startedAtMs,
					{ taskId: String(taskId) }
				)
				onTaskStatusChange?.({
					fileId,
					status: response.status,
					response,
					error_message: response.error_message
				})

				if (response.status === 'completed' || response.status === 'failed') {
					if (response.status === 'failed') {
						updateQueueItem(
							fileId,
							'failed',
							response.error_message,
							undefined,
							undefined,
							duration,
							startedAtMs
						)
					}
					return
				}
				await new Promise(resolve => setTimeout(resolve, 1500))
			} catch (error: any) {
				if (cancelledIdsRef.current.has(fileId)) return
				consecutiveErrors += 1
				const message = error.response?.data?.message || error.message || 'No se pudo consultar la tarea'
				const isTransient =
					!error.response &&
					(String(message).includes('timeout') ||
						String(message).includes('Network') ||
						error.code === 'ECONNABORTED' ||
						error.code === 'ERR_NETWORK')

				if (isTransient && consecutiveErrors < 30) {
					updateQueueItem(
						fileId,
						'processing',
						null,
						undefined,
						`Esperando al servidor… (reintento ${consecutiveErrors})`
					)
					await new Promise(resolve => setTimeout(resolve, 3000))
					continue
				}

				updateQueueItem(fileId, 'failed', message)
				onTaskStatusChange?.({ fileId, status: 'failed', response: null, error_message: message })
				return
			}
		}
	}

	const processFile = async (uploadedFile: UploadedFile) => {
		if (cancelledIdsRef.current.has(uploadedFile.id)) return

		updateQueueItem(uploadedFile.id, 'uploading')
		const controller = new AbortController()
		uploadAbortRef.current.set(uploadedFile.id, controller)

		try {
			const response = await uploadTask(
				{
					file: uploadedFile.file,
					ocr_profile: ocrProfileRef.current
				},
				{ signal: controller.signal }
			)
			uploadAbortRef.current.delete(uploadedFile.id)

			if (cancelledIdsRef.current.has(uploadedFile.id)) return

			const taskId = String(response.task_id)
			if (!taskId) throw new Error('El servidor no devolvió un identificador de tarea')

			taskIdsRef.current.set(uploadedFile.id, taskId)
			updateQueueItem(uploadedFile.id, 'pending', null, undefined, undefined, undefined, undefined, {
				taskId
			})
			onTaskStatusChange?.({ fileId: uploadedFile.id, status: 'pending', response: null })
			await pollTask(uploadedFile.id, taskId)
		} catch (error: any) {
			uploadAbortRef.current.delete(uploadedFile.id)
			if (
				cancelledIdsRef.current.has(uploadedFile.id) ||
				error?.code === 'ERR_CANCELED' ||
				error?.name === 'CanceledError' ||
				error?.name === 'AbortError'
			) {
				markCancelled(uploadedFile.id)
				return
			}
			const message = error.response?.data?.message || error.message || 'El archivo no pudo procesarse'
			updateQueueItem(uploadedFile.id, 'failed', message)
			onTaskStatusChange?.({
				fileId: uploadedFile.id,
				status: 'failed',
				response: null,
				error_message: message
			})
		}
	}

	const processBatch = async (files: UploadedFile[]) => {
		let nextIndex = 0
		const worker = async () => {
			while (nextIndex < files.length) {
				const index = nextIndex++
				const file = files[index]
				if (cancelledIdsRef.current.has(file.id)) continue
				await processFile(file)
			}
		}
		const workerCount = Math.min(MAX_CONCURRENT_FILES, files.length)
		await Promise.all(Array.from({ length: workerCount }, () => worker()))
	}

	const enqueueReadyFiles = (files: File[], sourceOriginal?: File | null) => {
		if (files.length === 0) return
		const newItems = files.map(file => ({
			file: {
				id: createFileId(file),
				name: file.name,
				size: file.size,
				type: file.type,
				file,
				uploadTime: new Date(),
				error: null,
				sourceOriginal: sourceOriginal ?? null
			},
			status: 'queued' as QueueStatus
		}))

		setQueue(items => [...items, ...newItems])
		newItems.forEach(item => onFileUploaded(item.file))
		setActiveBatches(n => n + 1)
		void processBatch(newItems.map(item => item.file)).finally(() => {
			if (mountedRef.current) setActiveBatches(n => Math.max(0, n - 1))
		})
	}

	const shiftCropQueue = () => {
		setCropQueue(prev => {
			const next = prev.slice(1)
			if (next.length === 0) setCropBatchTotal(0)
			return next
		})
	}

	const reopenForMoreCrop = (original: File) => {
		setCropQueue(prev => {
			if (prev[0] === original) return prev
			const alreadyQueued = prev.includes(original)
			if (!alreadyQueued) setCropBatchTotal(t => t + 1)
			return [original, ...prev.filter(f => f !== original)]
		})
	}

	const addFiles = (files: File[]) => {
		const existingKeys = new Set(
			queue.map(item => `${item.file.name}-${item.file.size}-${item.file.file.lastModified}`)
		)
		const validFiles: File[] = []

		for (const file of files) {
			const key = `${file.name}-${file.size}-${file.lastModified}`
			if (existingKeys.has(key)) continue
			if (!isValidFileType(file)) {
				toast.error(`${file.name}: formato no soportado. Usa ${ALLOWED_EXTENSIONS.join(', ')}`)
				continue
			}
			if (file.size > MAX_FILE_SIZE) {
				toast.error(`${file.name}: supera el límite de ${formatFileSize(MAX_FILE_SIZE)}`)
				continue
			}
			existingKeys.add(key)
			validFiles.push(file)
		}

		if (validFiles.length === 0) return

		if (!cropEnabled) {
			enqueueReadyFiles(validFiles)
			return
		}

		const images = validFiles.filter(isImageFile)
		const others = validFiles.filter(f => !isImageFile(f))

		if (others.length > 0) {
			if (images.length > 0) {
				toast.message('Los PDF se envían sin recorte; las imágenes se abren para seleccionar área.')
			}
			enqueueReadyFiles(others)
		}

		if (images.length === 0) return

		setCropQueue(prev => [...prev, ...images])
		setCropBatchTotal(t => t + images.length)
	}

	const handleDrop = (event: DragEvent) => {
		event.preventDefault()
		setIsDragging(false)
		addFiles(Array.from(event.dataTransfer.files))
	}

	const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
		addFiles(Array.from(event.target.files ?? []))
		event.target.value = ''
	}

	const clearCompleted = () => {
		setQueue(items =>
			items.filter(
				item =>
					item.status !== 'completed' &&
					item.status !== 'failed' &&
					item.status !== 'cancelled'
			)
		)
	}

	return (
		<div className='h-full flex flex-col bg-white dark:bg-gray-900 border-r border-border'>
			<div className='p-4'>
				<div className='mb-4 flex items-center justify-between gap-2'>
					<h2 className='text-lg font-semibold'>Procesamiento OCR</h2>
					<ThemeToggle />
				</div>

				<div className='mb-3'>
					<label className='block text-xs font-medium text-gray-600 dark:text-gray-300 mb-1.5'>
						Perfil de OCR
					</label>
					<div className='grid grid-cols-3 gap-1.5' role='radiogroup' aria-label='Perfil de OCR'>
						{OCR_PROFILES.map(profile => {
							const active = ocrProfile === profile.id
							return (
								<button
									key={profile.id}
									type='button'
									role='radio'
									aria-checked={active}
									disabled={isLoading}
									onClick={() => setOcrProfile(profile.id)}
									className={cn(
										'rounded-md border px-1.5 py-2 text-center transition-colors',
										active
											? 'border-primary bg-primary/10 text-foreground'
											: 'border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:border-primary/50',
										isLoading && 'opacity-60 cursor-not-allowed'
									)}>
									<span className='block text-xs font-semibold leading-tight'>{profile.label}</span>
									<span className='block text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 leading-tight'>
										{profile.hint}
									</span>
								</button>
							)
						})}
					</div>
				</div>

				<button
					type='button'
					role='switch'
					aria-checked={cropEnabled}
					disabled={cropQueue.length > 0}
					onClick={() => setCropEnabled(v => !v)}
					className={cn(
						'mb-3 w-full flex items-start gap-2.5 rounded-md border px-3 py-2.5 text-left transition-colors',
						cropEnabled
							? 'border-primary bg-primary/10'
							: 'border-gray-300 dark:border-gray-700 hover:border-primary/50',
						cropQueue.length > 0 && 'opacity-60 cursor-not-allowed'
					)}>
					<Crop
						className={cn(
							'size-4 mt-0.5 shrink-0',
							cropEnabled ? 'text-primary' : 'text-gray-500 dark:text-gray-400'
						)}
					/>
					<span className='min-w-0'>
						<span className='block text-xs font-semibold text-foreground'>
							Recortar área antes del OCR
						</span>
						<span className='block text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 leading-snug'>
							{cropEnabled
								? 'Activo: al subir imágenes podrás marcar la zona útil'
								: 'Inactivo: se envía la imagen completa'}
						</span>
					</span>
				</button>

				<div
					className={cn(
						'border-2 border-dashed rounded-lg py-6 px-4 text-center cursor-pointer transition-colors',
						isDragging ? 'border-primary bg-primary/5' : 'border-gray-300 dark:border-gray-700 hover:border-primary/50'
					)}
					onDragOver={event => { event.preventDefault(); if (!isLoading) setIsDragging(true) }}
					onDragLeave={() => setIsDragging(false)}
					onDrop={handleDrop}
					onClick={() => fileInputRef.current?.click()}>
					{cropOpen ? (
						<Crop className='size-10 mx-auto mb-3 text-primary' />
					) : isLoading ? (
						<Loader2 className='size-10 mx-auto mb-3 text-primary animate-spin' />
					) : (
						<Upload className='size-10 mx-auto mb-3 text-gray-400' />
					)}
					<p className='text-sm font-medium mb-1'>
						{cropOpen
							? 'Selecciona el área a procesar…'
							: isLoading
								? 'Procesando lote...'
								: 'Selecciona o arrastra archivos'}
					</p>
					<p className='text-xs text-gray-500'>También puedes seleccionar una carpeta</p>
					<p className='text-xs text-gray-400 mt-1'>PNG/JPG/JPEG/PDF · máximo 20 MB por archivo</p>
				</div>

				<div className='grid grid-cols-2 gap-2 mt-3'>
					<button type='button' className='flex items-center justify-center gap-1 rounded-md border px-2 py-2 text-xs hover:bg-gray-50 dark:hover:bg-gray-800' onClick={() => fileInputRef.current?.click()} disabled={isLoading}>
						<FileText className='size-4' /> Archivos
					</button>
					<button type='button' className='flex items-center justify-center gap-1 rounded-md border px-2 py-2 text-xs hover:bg-gray-50 dark:hover:bg-gray-800' onClick={() => directoryInputRef.current?.click()} disabled={isLoading}>
						<FolderOpen className='size-4' /> Carpeta
					</button>
				</div>

				<input
					ref={fileInputRef}
					type='file'
					className='hidden'
					accept='image/png,image/jpeg,.jpg,.jpeg,.png,.pdf'
					multiple
					onChange={handleInput}
				/>
				{/* webkitdirectory is supported by Chromium-based browsers for folder selection. */}
				<input
					ref={directoryInputRef}
					type='file'
					className='hidden'
					accept='image/png,image/jpeg,.jpg,.jpeg,.png,.pdf'
					multiple
					onChange={handleInput}
					{...({ webkitdirectory: '', directory: '' } as any)}
				/>
			</div>

			<ImageCropDialog
				open={cropOpen}
				file={cropFile}
				queueLabel={
					cropBatchTotal > 1
						? `(${cropDoneCount + 1} de ${cropBatchTotal}) · ${cropFile?.name ?? ''}`
						: cropFile?.name
				}
				onConfirm={(cropped, { continueOnSameFile }) => {
					enqueueReadyFiles([cropped], cropFile)
					if (!continueOnSameFile) shiftCropQueue()
				}}
				onUseFull={original => {
					enqueueReadyFiles([original])
					shiftCropQueue()
				}}
				onDoneWithFile={() => {
					shiftCropQueue()
				}}
				onCancel={() => {
					toast.message(`Omitido: ${cropFile?.name ?? 'archivo'}`)
					shiftCropQueue()
				}}
			/>

			{queue.length > 0 && (
				<div className='flex-1 min-h-0 px-3 pb-3 flex flex-col'>
					<div className='flex items-center justify-between text-xs mb-2'>
						<span className='font-medium'>{finishedCount}/{queue.length} terminados</span>
						<span className='text-gray-500'>{Math.round(progress)}%</span>
					</div>
					<div className='h-2 rounded-full bg-gray-200 dark:bg-gray-700 mb-3 overflow-hidden'>
						<div className='h-full bg-primary transition-all' style={{ width: `${progress}%` }} />
					</div>
					<div className='flex items-center justify-between mb-2'>
						<span className='text-xs text-gray-500'>{queue.length} archivo{queue.length === 1 ? '' : 's'}</span>
						<button type='button' className='text-xs text-gray-500 hover:text-foreground' onClick={clearCompleted}>Limpiar terminados</button>
					</div>
					<div className='space-y-1 overflow-y-auto pr-1'>
						{queue.map(item => (
							<div key={item.file.id} className='rounded-md border px-2 py-2 text-xs'>
								<div className='flex items-center gap-2 min-w-0'>
									{item.status === 'completed' ? (
										<CheckCircle2 className='size-4 text-green-600 dark:text-green-400 shrink-0' />
									) : item.status === 'failed' ? (
										<XCircle className='size-4 text-red-600 dark:text-red-400 shrink-0' />
									) : item.status === 'cancelled' ? (
										<Square className='size-3.5 text-amber-600 dark:text-amber-400 shrink-0 fill-current' />
									) : (
										<Loader2 className='size-4 text-primary shrink-0 animate-spin' />
									)}
									<span className='truncate flex-1' title={item.file.name}>{item.file.name}</span>
									{STOPPABLE.has(item.status) && (
										<button
											type='button'
											title='Detener este proceso'
											aria-label={`Detener ${item.file.name}`}
											disabled={item.stopping}
											onClick={e => {
												e.stopPropagation()
												stopQueueItem(item.file.id)
											}}
											className={cn(
												'shrink-0 inline-flex items-center justify-center rounded border border-red-300 dark:border-red-800',
												'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300',
												'hover:bg-red-100 dark:hover:bg-red-900/50 size-6',
												'disabled:opacity-50 disabled:cursor-not-allowed'
											)}>
											{item.stopping ? (
												<Loader2 className='size-3 animate-spin' />
											) : (
												<Square className='size-2.5 fill-current' />
											)}
										</button>
									)}
									<span className='text-gray-500 dark:text-gray-400 shrink-0 tabular-nums'>
										{(() => {
											const live = liveSecondsFor(item)
											if (item.status === 'completed' && live != null) {
												return formatDuration(live)
											}
											if (item.status === 'cancelled') {
												return statusLabel.cancelled
											}
											if (
												(item.status === 'processing' || item.status === 'pending') &&
												live != null
											) {
												const pct =
													typeof item.progress === 'number'
														? `${Math.round(item.progress)}% · `
														: ''
												return `${pct}${formatDuration(live)}`
											}
											if (item.status === 'processing' && typeof item.progress === 'number') {
												return `${Math.round(item.progress)}%`
											}
											return statusLabel[item.status]
										})()}
									</span>
								</div>
								{(item.status === 'processing' || item.status === 'pending') && (
									<>
										<div className='mt-1.5 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden'>
											<div
												className='h-full bg-primary transition-all'
												style={{ width: `${Math.min(100, Math.max(0, item.progress ?? 5))}%` }}
											/>
										</div>
										{item.currentStep && (
											<p className='text-gray-500 dark:text-gray-400 mt-1 truncate' title={item.currentStep}>
												{item.currentStep}
											</p>
										)}
									</>
								)}
								{item.error && <p className='text-red-500 mt-1 break-words'>{item.error}</p>}
								{(item.file.sourceOriginal ||
									(isImageFile(item.file.file) && !item.file.name.includes('_zona'))) && (
									<button
										type='button'
										className='mt-1.5 inline-flex items-center gap-1 text-[11px] text-primary hover:underline disabled:opacity-50'
										disabled={cropFile === (item.file.sourceOriginal || item.file.file)}
										onClick={() =>
											reopenForMoreCrop(item.file.sourceOriginal || item.file.file)
										}>
										<Crop className='size-3' />
										Otra zona del original
									</button>
								)}
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	)
}
