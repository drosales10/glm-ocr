import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

// Subida: timeout moderado. El OCR en sí es asíncrono (cola de tareas).
const api = axios.create({
	baseURL: BASE_URL,
	timeout: 120000
})

// Polling de estado: sin timeout de cliente (el OCR puede durar >10 min).
const statusApi = axios.create({
	baseURL: BASE_URL,
	timeout: 0
})

api.interceptors.response.use(
	response => response,
	error => {
		if (error.response) {
			console.error('API Error:', error.response.data)
		} else if (error.request) {
			console.error('Network Error:', error.request)
		} else {
			console.error('Error:', error.message)
		}
		return Promise.reject(error)
	}
)

statusApi.interceptors.response.use(
	response => response,
	error => Promise.reject(error)
)

export interface ApiResponse<T> {
	success: boolean
	data: T
	message?: string | null
	error?: string | null
}

export interface UploadTaskData {
	task_id: string | number
	document_id: string
	created_at: string
	priority: string | number
	status: string
	error?: string | null
	message?: string | null
}

export interface UploadTaskResponse extends ApiResponse<UploadTaskData> {}

export type OcrProfile = 'fast' | 'balanced' | 'math'

export interface UploadTaskParams {
	file: File
	custom_url?: string
	/** Perfil de velocidad/calidad enviado al pipeline glmocr. */
	ocr_profile?: OcrProfile
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TaskStatusData {
	task_id: string | number
	document_id: string
	status: TaskStatus
	progress?: number
	current_step?: string | null
	current_stage?: string | null
	created_at: string
	started_at?: string
	completed_at?: string
	/** Segundos entre inicio y fin del OCR (si la tarea ya terminó). */
	execution_time?: number | null
	error_message?: string | null
	result_file_path?: string
	result?: {
		output_path?: string
		output_files?: string[]
		metadata?: {
			total_pages?: number
			total_text_length?: number
			word_count?: number
			processing_mode?: string
			source_type?: string
		}
		execution_time?: number
		stage_results?: any
	}
	priority: number
	full_markdown?: string
	metadata?: {
		task_id?: string
		document_id?: string
		original_filename?: string
		processing_mode?: string
		total_pages?: number
		merge_timestamp?: number
		width?: number
		height?: number
	}
	layout?: Array<{
		block_content: string
		bbox: [number, number, number, number]
		block_id: number
		text_length?: number | null
		page_index: number
	}>
	images?: Record<string, string>
}

export interface TaskStatusResponse extends ApiResponse<TaskStatusData> {}

export async function uploadTask(params: UploadTaskParams): Promise<UploadTaskData> {
	const formData = new FormData()
	formData.append('file', params.file)
	formData.append('processing_mode', 'pipeline')
	formData.append('ocr_profile', params.ocr_profile || 'balanced')
	if (params.custom_url) {
		formData.append('custom_url', params.custom_url)
	}

	const response = await api.post<UploadTaskResponse>('/tasks/upload', formData)

	if (!response.data.success) {
		throw new Error(response.data.message || 'Error al subir el archivo')
	}

	return response.data.data
}

const STEP_LABELS: Record<string, string> = {
	pdf_to_image: 'Preparando la imagen',
	layout_and_ocr: 'Reconociendo el texto',
	result_merge: 'Uniendo el resultado'
}

export function formatStep(step?: string | null): string | null {
	if (!step) return null
	return STEP_LABELS[step] ?? step
}

export async function getTaskStatus(taskId: string | number): Promise<TaskStatusData> {
	const response = await statusApi.get<TaskStatusResponse>(`/tasks/${taskId}`)

	if (!response.data.success) {
		throw new Error(response.data.message || 'Error al consultar el estado de la tarea')
	}

	return response.data.data
}

export default api
