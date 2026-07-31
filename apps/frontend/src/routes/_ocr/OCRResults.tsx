import { useEffect, useMemo } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { TaskResponse } from './FileUpload'
import { MarkdownPreview } from '@/components/ocr/MarkdownPreview'
import { useOcrStore } from '../../store/useOcrStore'
import { AppWindowIcon, CopyIcon, DownloadIcon, FileJsonIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { JsonPreview } from '@/components/ocr/JsonPreview'
// import { data as mockData } from './data'

interface OCRResultsProps {
	result: TaskResponse | null
	fileName?: string
}

export function OCRResults({ result, fileName }: OCRResultsProps) {
	const setBlocks = useOcrStore(s => s.setBlocks)

	// Obtener layout e images de los datos reales; si no hay, usar datos mock
	const layout = useMemo(() => result?.response?.layout || [], [result?.response?.layout])
	const images = useMemo(() => result?.response?.images || {}, [result?.response?.images])


	// Obtener la altura de una página PDF
	const pageHeight = result?.response?.metadata?.height ?? 2339

	// Convertir layout al formato de blocks (filtrar contenido que solo tiene #; conservar imágenes)
	const blocks = useMemo(() => {
		if (result?.status !== 'completed') {
			return []
		}
		return layout
			.filter((b: any) => {
				// Filtrar contenido vacío o que solo contiene #
				if (!b.block_content || b.block_content.trim() === '') {
					return false
				}
				return true
			})
			.map((b: any, index: number) => {
				const blockContent = b.block_content.trim()

				// Procesar coordenadas bbox: siempre usar coordenadas relativas (dentro de cada página)
				let bbox: [number, number, number, number] | null = null
				let width = 0
				let height = 0
				if (b.bbox) {
					const [x1, y1, x2, y2] = b.bbox as [number, number, number, number]
					width = x2 - x1
					height = y2 - y1

					// Siempre usar coordenadas relativas (dentro de cada página)
					bbox = [x1, y1, x2, y2]
				}

				return {
					id: b.block_id ?? index + Math.random() * 1000000,
					content: blockContent,
					bbox,
					pageIndex: b.page_index ?? 1,
					isImage: blockContent.startsWith('![]('), // Marcar si es una imagen
					width: width,
					height: height
				}
			})
	}, [layout, images, pageHeight, result?.status])

	// Guardar los blocks en el store
	useEffect(() => {
		if (blocks.length > 0) {
			setBlocks(blocks)
		}
	}, [blocks, setBlocks])

	const handleCopy = () => {
		if (!result?.response?.full_markdown) return
		navigator.clipboard.writeText(result.response.full_markdown)
		toast.success('Copiado correctamente')
	}

	const handleDownload = () => {
		if (!result?.response?.full_markdown) return
		const blob = new Blob([result.response.full_markdown], { type: 'text/markdown' })
		const url = URL.createObjectURL(blob)
		const a = document.createElement('a')
		a.href = url
		a.download = `${fileName || 'result'}.md`
		a.click()
		URL.revokeObjectURL(url)
		toast.success('Descarga completada')
	}

	const response = result?.response
	const status = result?.status
	const error_message = result?.error_message

	return (
		<div className='h-screen flex flex-col bg-white border-l border-border'>
			<Tabs defaultValue='markdown' className='flex-1 flex flex-col overflow-hidden'>
				{/* TabsList fijo en la parte superior */}
				<div className='px-4 pt-4 pb-0 bg-white sticky top-0 z-10 flex items-center justify-between'>
					<TabsList className='grid grid-cols-2'>
						<TabsTrigger value='markdown' className='cursor-pointer'>
							<AppWindowIcon className='size-4' />Markdown</TabsTrigger>
						<TabsTrigger value='json' className='cursor-pointer'>
							<FileJsonIcon className='size-4' />JSON</TabsTrigger>
					</TabsList>
					{status === 'completed' && <div className='flex items-center gap-2'>
						<Button variant="outline" size="icon" className='cursor-pointer' onClick={() => handleCopy()}>
							<CopyIcon className='size-4' />
						</Button>
						<Button variant="outline" size="icon" className='cursor-pointer' onClick={() => handleDownload()}>
							<DownloadIcon className='size-4' />
						</Button>
					</div>}
				</div>

				{/* Área de contenido con scroll */}
				<div className='flex-1 overflow-hidden'>
					<TabsContent value='markdown' className='h-full m-0 mt-0'>
						{/* Estado de procesamiento */}
						{status === 'pending' || status === 'processing' ? (
							<div className='h-full flex items-center justify-center'>
								<div className='text-center max-w-sm px-4'>
									<div className='inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4'></div>
									<p className='text-gray-500 dark:text-gray-400'>
										Procesando...
										{typeof response?.progress === 'number' ? ` ${Math.round(response.progress)}%` : ''}
									</p>
									{(response?.current_step || response?.current_stage) && (
										<p className='text-xs text-gray-400 mt-2'>
											{response.current_step || response.current_stage}
										</p>
									)}
									<p className='text-xs text-gray-400 mt-3'>
										Una página densa puede tardar 1–5 minutos (layout + OCR por región).
									</p>
								</div>
							</div>
						) : blocks.length > 0 && status === 'completed' ? (
							// Procesamiento exitoso
							<MarkdownPreview />
						) : status === 'completed' ? (
							// Completado sin contenido
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
									<p>No hay contenido Markdown</p>
								</div>
							</div>
						) : status === 'failed' ? (
							// Fallo del procesamiento
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-red-500 dark:text-red-400'>
									<p>Error al procesar</p>
									{error_message && (
										<p className='text-sm mt-2 text-gray-500 dark:text-gray-400'>
											{error_message}
										</p>
									)}
								</div>
							</div>
						) : (
							// Sin archivo
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
									<p>Sube un archivo y espera a que termine el procesamiento</p>
								</div>
							</div>
						)}
					</TabsContent>

					<TabsContent value='json' className='h-full m-0 mt-0 overflow-auto'>
						<div className='p-4'>
							{response && status === 'completed' && result?.response ? (
								<div className='bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-auto'>
									<JsonPreview json={response} />
								</div>
							) : (
								<div className='h-full flex items-center justify-center'>
									<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
										<p>Sin datos</p>
									</div>
								</div>
							)}
						</div>
					</TabsContent>
				</div>
			</Tabs>
		</div>
	)
}
