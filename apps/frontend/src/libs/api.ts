import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Crear instancia de axios
const api = axios.create({
	baseURL: BASE_URL,
	timeout: 60000 // Timeout de 60 segundos
})

// Interceptor de peticiones
api.interceptors.request.use(
	config => {
		// Aquí se puede añadir token u otra información de autenticación
		return config
	},
	error => {
		return Promise.reject(error)
	}
)

// Interceptor de respuestas
api.interceptors.response.use(
	response => {
		return response
	},
	error => {
		// Manejo unificado de errores
		if (error.response) {
			// El servidor devolvió un código de estado de error
			console.error('API Error:', error.response.data)
		} else if (error.request) {
			// La petición se envió pero no se recibió respuesta
			console.error('Network Error:', error.request)
		} else {
			// Otros errores
			console.error('Error:', error.message)
		}
		return Promise.reject(error)
	}
)

// Formato unificado de respuesta de la API
export interface ApiResponse<T> {
	success: boolean
	data: T
	message?: string | null
	error?: string | null
}

// Estructura de data devuelta por el endpoint de subida
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

export interface UploadTaskParams {
	file: File
	custom_url?: string
}

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed'

// Estructura de data devuelta por el endpoint de polling
export interface TaskStatusData {
	task_id: string | number
	document_id: string
	status: TaskStatus
	progress?: number
	current_stage?: string | null
	created_at: string
	started_at?: string
	completed_at?: string
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

/**
 * Sube un archivo y crea una tarea OCR
 * @param params Parámetros de subida
 * @returns Promise<UploadTaskData>
 */
export async function uploadTask(params: UploadTaskParams): Promise<UploadTaskData> {
	const formData = new FormData()
	formData.append('file', params.file)
	formData.append('processing_mode', 'pipeline')
	if (params.custom_url) {
		formData.append('custom_url', params.custom_url)
	}

	const response = await api.post<UploadTaskResponse>('/tasks/upload', formData)

	if (!response.data.success) {
		throw new Error(response.data.message || 'Error al subir el archivo')
	}

	return response.data.data
}

/**
 * Consulta el estado de una tarea
 * @param taskId ID de la tarea
 * @returns Promise<TaskStatusData>
 */
export async function getTaskStatus(taskId: string | number): Promise<TaskStatusData> {
	const response = await api.get<TaskStatusResponse>(`/tasks/${taskId}`)

	if (!response.data.success) {
		throw new Error(response.data.message || 'Error al consultar el estado de la tarea')
	}

	return response.data.data
}

export default api
