import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { CheckCircle2, FileText, FolderOpen, Loader2, Upload, XCircle } from 'lucide-react'
import { cn } from '@/libs/utils'
import { getTaskStatus, uploadTask, type TaskStatusData, type TaskStatus } from '@/libs/api'
import { toast } from 'sonner'

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
}

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
	failed: 'Fallido'
}

export function FileUpload({ onFileUploaded, onTaskStatusChange }: FileUploadProps) {
	const [queue, setQueue] = useState<QueueItem[]>([])
	const [isDragging, setIsDragging] = useState(false)
	const [isLoading, setIsLoading] = useState(false)
	const fileInputRef = useRef<HTMLInputElement>(null)
	const directoryInputRef = useRef<HTMLInputElement>(null)
	const mountedRef = useRef(true)

	useEffect(() => {
		mountedRef.current = true
		return () => {
			mountedRef.current = false
		}
	}, [])

	const completedCount = useMemo(
		() => queue.filter(item => item.status === 'completed').length,
		[queue]
	)
	const failedCount = useMemo(
		() => queue.filter(item => item.status === 'failed').length,
		[queue]
	)
	const progress = queue.length === 0 ? 0 : ((completedCount + failedCount) / queue.length) * 100

	const updateQueueItem = (
		fileId: string,
		status: QueueStatus,
		error?: string | null,
		progress?: number,
		currentStep?: string | null
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
							currentStep: currentStep ?? item.currentStep
						}
					: item
			)
		)
	}

	const pollTask = async (fileId: string, taskId: string | number) => {
		let consecutiveErrors = 0
		while (mountedRef.current) {
			try {
				let response = await getTaskStatus(taskId)
				consecutiveErrors = 0

				// Evitar carrera: a veces status=completed llega antes de merged.json
				if (
					response.status === 'completed' &&
					!response.full_markdown &&
					!(response.layout && response.layout.length)
				) {
					await new Promise(resolve => setTimeout(resolve, 800))
					response = await getTaskStatus(taskId)
				}

				const step = response.current_step ?? response.current_stage ?? null
				updateQueueItem(fileId, response.status, null, response.progress, step)
				onTaskStatusChange?.({
					fileId,
					status: response.status,
					response,
					error_message: response.error_message
				})

				if (response.status === 'completed' || response.status === 'failed') {
					if (response.status === 'failed') {
						updateQueueItem(fileId, 'failed', response.error_message)
					}
					return
				}
				await new Promise(resolve => setTimeout(resolve, 2000))
			} catch (error: any) {
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
		updateQueueItem(uploadedFile.id, 'uploading')
		try {
			const response = await uploadTask({ file: uploadedFile.file })
			const taskId = String(response.task_id)
			if (!taskId) throw new Error('El servidor no devolvió un identificador de tarea')

			updateQueueItem(uploadedFile.id, 'pending')
			onTaskStatusChange?.({ fileId: uploadedFile.id, status: 'pending', response: null })
			await pollTask(uploadedFile.id, taskId)
		} catch (error: any) {
			const message = error.response?.data?.message || error.message || 'El archivo no pudo procesarse'
			updateQueueItem(uploadedFile.id, 'failed', message)
			onTaskStatusChange?.({ fileId: uploadedFile.id, status: 'failed', response: null, error_message: message })
		}
	}

	const processBatch = async (files: UploadedFile[]) => {
		let nextIndex = 0
		const worker = async () => {
			while (nextIndex < files.length) {
				const index = nextIndex++
				await processFile(files[index])
			}
		}
		const workerCount = Math.min(MAX_CONCURRENT_FILES, files.length)
		await Promise.all(Array.from({ length: workerCount }, () => worker()))
	}

	const addFiles = (files: File[]) => {
		const existingKeys = new Set(queue.map(item => `${item.file.name}-${item.file.size}-${item.file.file.lastModified}`))
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
		const newItems = validFiles.map(file => ({
			file: {
				id: createFileId(file),
				name: file.name,
				size: file.size,
				type: file.type,
				file,
				uploadTime: new Date(),
				error: null
			},
			status: 'queued' as QueueStatus
		}))

		setQueue(items => [...items, ...newItems])
		newItems.forEach(item => onFileUploaded(item.file))
		setIsLoading(true)
		void processBatch(newItems.map(item => item.file)).finally(() => {
			if (mountedRef.current) setIsLoading(false)
		})
	}

	const handleDrop = (event: DragEvent) => {
		if (isLoading) return
		event.preventDefault()
		setIsDragging(false)
		addFiles(Array.from(event.dataTransfer.files))
	}

	const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
		if (isLoading) return
		addFiles(Array.from(event.target.files ?? []))
		event.target.value = ''
	}

	const clearCompleted = () => {
		setQueue(items => items.filter(item => item.status !== 'completed' && item.status !== 'failed'))
	}

	return (
		<div className='h-full flex flex-col bg-white dark:bg-gray-900 border-r border-border'>
			<div className='p-4'>
				<h2 className='text-lg font-semibold mb-4'>Procesamiento OCR</h2>
				<div
					className={cn(
						'border-2 border-dashed rounded-lg py-6 px-4 text-center cursor-pointer transition-colors',
						isDragging ? 'border-primary bg-primary/5' : 'border-gray-300 dark:border-gray-700 hover:border-primary/50'
					)}
					onDragOver={event => { event.preventDefault(); if (!isLoading) setIsDragging(true) }}
					onDragLeave={() => setIsDragging(false)}
					onDrop={handleDrop}
					onClick={() => fileInputRef.current?.click()}>
					{isLoading ? <Loader2 className='size-10 mx-auto mb-3 text-primary animate-spin' /> : <Upload className='size-10 mx-auto mb-3 text-gray-400' />}
					<p className='text-sm font-medium mb-1'>{isLoading ? 'Procesando lote...' : 'Selecciona o arrastra archivos'}</p>
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

				<input ref={fileInputRef} type='file' className='hidden' accept='image/png,image/jpeg,.jpg,.jpeg,.png,.pdf' multiple disabled={isLoading} onChange={handleInput} />
				{/* webkitdirectory is supported by Chromium-based browsers for folder selection. */}
				<input ref={directoryInputRef} type='file' className='hidden' accept='image/png,image/jpeg,.jpg,.jpeg,.png,.pdf' multiple disabled={isLoading} onChange={handleInput} {...({ webkitdirectory: '', directory: '' } as any)} />
			</div>

			{queue.length > 0 && (
				<div className='flex-1 min-h-0 px-3 pb-3 flex flex-col'>
					<div className='flex items-center justify-between text-xs mb-2'>
						<span className='font-medium'>{completedCount + failedCount}/{queue.length} terminados</span>
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
									{item.status === 'completed' ? <CheckCircle2 className='size-4 text-green-600 shrink-0' /> : item.status === 'failed' ? <XCircle className='size-4 text-red-600 shrink-0' /> : <Loader2 className='size-4 text-primary shrink-0 animate-spin' />}
									<span className='truncate flex-1' title={item.file.name}>{item.file.name}</span>
									<span className='text-gray-500 shrink-0'>
										{item.status === 'processing' && typeof item.progress === 'number'
											? `${Math.round(item.progress)}%`
											: statusLabel[item.status]}
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
											<p className='text-gray-500 mt-1 truncate' title={item.currentStep}>
												{item.currentStep}
											</p>
										)}
									</>
								)}
								{item.error && <p className='text-red-500 mt-1 break-words'>{item.error}</p>}
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	)
}
