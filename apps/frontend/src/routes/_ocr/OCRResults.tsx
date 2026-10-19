import { useEffect, useMemo, useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { TaskResponse } from './FileUpload'
import { MarkdownPreview } from '@/components/ocr/MarkdownPreview'
import { useOcrStore } from '../../store/useOcrStore'
import { AppWindowIcon, ClockIcon, CopyIcon, DownloadIcon, FileJsonIcon, LanguagesIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { JsonPreview } from '@/components/ocr/JsonPreview'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import rehypeRaw from 'rehype-raw'
import 'katex/dist/katex.min.css'
import { formatDuration, getOcrDurationSeconds, parseUtcMs } from '@/libs/utils'
import { formatStep, getTranslateLanguages, translateText, type TranslateLanguage } from '@/libs/api'
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue
} from '@/components/ui/select'

const FALLBACK_LANGUAGES: TranslateLanguage[] = [
	{ code: 'es', name: 'Español' },
	{ code: 'en', name: 'Inglés' },
	{ code: 'fr', name: 'Francés' },
	{ code: 'de', name: 'Alemán' },
	{ code: 'it', name: 'Italiano' },
	{ code: 'pt', name: 'Portugués' },
	{ code: 'ru', name: 'Ruso' },
	{ code: 'zh', name: 'Chino' },
	{ code: 'ja', name: 'Japonés' },
	{ code: 'ko', name: 'Coreano' },
	{ code: 'ar', name: 'Árabe' },
	{ code: 'hi', name: 'Hindi' },
	{ code: 'nl', name: 'Neerlandés' },
	{ code: 'pl', name: 'Polaco' },
	{ code: 'tr', name: 'Turco' },
	{ code: 'vi', name: 'Vietnamita' },
	{ code: 'id', name: 'Indonesio' },
	{ code: 'uk', name: 'Ucraniano' },
	{ code: 'sv', name: 'Sueco' },
	{ code: 'th', name: 'Tailandés' }
]

interface TranslationEntry {
	text: string
	source: string
	target: string
	error: string | null
}

interface OCRResultsProps {
	result: TaskResponse | null
	fileName?: string
}

function parseBBox(raw: unknown): [number, number, number, number] | null {
	if (Array.isArray(raw) && raw.length >= 4) {
		const nums = raw.slice(0, 4).map(Number)
		if (nums.every(n => Number.isFinite(n))) {
			return nums as [number, number, number, number]
		}
	}
	if (typeof raw === 'string') {
		const nums = raw
			.trim()
			.split(/[\s,]+/)
			.map(Number)
		if (nums.length >= 4 && nums.every(n => Number.isFinite(n))) {
			return nums.slice(0, 4) as [number, number, number, number]
		}
	}
	return null
}

export function OCRResults({ result, fileName }: OCRResultsProps) {
	const setBlocks = useOcrStore(s => s.setBlocks)
	const [nowMs, setNowMs] = useState(() => Date.now())

	const layout = useMemo(() => result?.response?.layout || [], [result?.response?.layout])
	const pageHeight = result?.response?.metadata?.height ?? 2339

	const blocks = useMemo(() => {
		if (result?.status !== 'completed') {
			return []
		}
		return layout
			.filter((b: any) => b?.block_content && String(b.block_content).trim() !== '')
			.map((b: any, index: number) => {
				const blockContent = String(b.block_content).trim()
				const bbox = parseBBox(b.bbox)
				const width = bbox ? bbox[2] - bbox[0] : 0
				const height = bbox ? bbox[3] - bbox[1] : 0

				return {
					id: b.block_id ?? index + 1,
					content: blockContent,
					bbox,
					pageIndex: b.page_index ?? 1,
					isImage: blockContent.startsWith('![](') || blockContent.includes('<img '),
					width,
					height
				}
			})
	}, [layout, pageHeight, result?.status])

	useEffect(() => {
		setBlocks(blocks)
	}, [blocks, setBlocks])

	const response = result?.response
	const status = result?.status
	const error_message = result?.error_message
	const markdown = response?.full_markdown?.trim() || ''
	const isDone = status === 'completed'
	const isBusy = status === 'pending' || status === 'processing'

	useEffect(() => {
		if (!isBusy) return
		const id = window.setInterval(() => setNowMs(Date.now()), 1000)
		return () => window.clearInterval(id)
	}, [isBusy])

	const durationSeconds = useMemo(() => {
		if (!response) return null
		if (isDone || status === 'failed') {
			return getOcrDurationSeconds(response, nowMs)
		}
		if (isBusy) {
			const start = parseUtcMs(response.started_at || response.created_at)
			if (start == null) return null
			return Math.max(0, (nowMs - start) / 1000)
		}
		return null
	}, [response, isDone, isBusy, status, nowMs])

	const durationLabel = durationSeconds != null ? formatDuration(durationSeconds) : null

	const taskKey = String(response?.task_id || result?.fileId || '')
	const [languages, setLanguages] = useState<TranslateLanguage[]>(FALLBACK_LANGUAGES)
	const [sourceLang, setSourceLang] = useState('en')
	const [targetLang, setTargetLang] = useState('es')
	const [tab, setTab] = useState('markdown')
	const [translations, setTranslations] = useState<Record<string, TranslationEntry>>({})
	const [translatingKey, setTranslatingKey] = useState<string | null>(null)

	const translation = taskKey ? translations[taskKey] : undefined
	const isTranslating = translatingKey === taskKey && translatingKey !== ''

	useEffect(() => {
		let cancelled = false
		getTranslateLanguages()
			.then(items => {
				if (!cancelled && items.length > 0) setLanguages(items)
			})
			.catch(() => {
				/* La lista local cubre el mismo conjunto si el backend no responde. */
			})
		return () => {
			cancelled = true
		}
	}, [])

	const activeText = tab === 'translation' ? translation?.text || '' : markdown

	const handleCopy = () => {
		if (tab === 'translation' && !translation?.text) {
			toast.error('Todavía no hay traducción')
			return
		}
		if (!activeText) return
		navigator.clipboard.writeText(activeText)
		toast.success('Copiado correctamente')
	}

	const handleDownload = () => {
		if (tab === 'translation' && !translation?.text) {
			toast.error('Todavía no hay traducción')
			return
		}
		if (!activeText) return
		const blob = new Blob([activeText], { type: 'text/markdown' })
		const url = URL.createObjectURL(blob)
		const a = document.createElement('a')
		const base = fileName || 'result'
		a.href = url
		a.download = tab === 'translation' ? `${base}.${translation?.target || targetLang}.md` : `${base}.md`
		a.click()
		URL.revokeObjectURL(url)
		toast.success('Descarga completada')
	}

	const handleTranslate = async () => {
		if (!markdown || !taskKey || isTranslating) return
		setTranslatingKey(taskKey)
		setTab('translation')
		setTranslations(current => ({
			...current,
			[taskKey]: {
				text: current[taskKey]?.text || '',
				source: sourceLang,
				target: targetLang,
				error: null
			}
		}))
		try {
			const data = await translateText({
				text: markdown,
				source_lang: sourceLang,
				target_lang: targetLang
			})
			setTranslations(current => ({
				...current,
				[taskKey]: {
					text: data.translated,
					source: data.source_lang,
					target: data.target_lang,
					error: null
				}
			}))
			toast.success('Traducción lista')
		} catch (error) {
			const message = error instanceof Error ? error.message : 'No se pudo traducir la transcripción'
			setTranslations(current => ({
				...current,
				[taskKey]: {
					text: current[taskKey]?.text || '',
					source: sourceLang,
					target: targetLang,
					error: message
				}
			}))
			toast.error(message)
		} finally {
			setTranslatingKey(current => (current === taskKey ? null : current))
		}
	}

	return (
		<div className='h-screen flex flex-col bg-white dark:bg-gray-950 border-l border-border'>
			<Tabs value={tab} onValueChange={setTab} className='flex-1 flex flex-col overflow-hidden'>
				<div className='px-4 pt-4 pb-3 bg-white dark:bg-gray-950 sticky top-0 z-10 flex flex-col gap-3'>
					<div className='flex flex-wrap items-center justify-between gap-3'>
					<TabsList className='grid grid-cols-3'>
						<TabsTrigger value='markdown' className='cursor-pointer'>
							<AppWindowIcon className='size-4' />
							Markdown
						</TabsTrigger>
						<TabsTrigger value='translation' className='cursor-pointer'>
							<LanguagesIcon className='size-4' />
							Traducción
						</TabsTrigger>
						<TabsTrigger value='json' className='cursor-pointer'>
							<FileJsonIcon className='size-4' />
							JSON
						</TabsTrigger>
					</TabsList>
					<div className='flex items-center gap-2 min-w-0'>
						{durationLabel && (
							<span
								className='inline-flex items-center gap-1.5 rounded-md border border-border bg-gray-50 dark:bg-gray-900 px-2 py-1 text-xs text-gray-600 dark:text-gray-300 tabular-nums'
								title={
									isBusy
										? 'Tiempo transcurrido desde el inicio del OCR'
										: 'Tiempo total que tardó el OCR en completarse'
								}>
								<ClockIcon className='size-3.5 shrink-0 text-gray-500 dark:text-gray-400' />
								{isBusy ? (
									<>
										<span className='text-gray-500 dark:text-gray-400'>Transcurrido</span>
										<span className='font-medium text-foreground'>{durationLabel}</span>
									</>
								) : (
									<>
										<span className='text-gray-500 dark:text-gray-400'>Generado en</span>
										<span className='font-medium text-foreground'>{durationLabel}</span>
									</>
								)}
							</span>
						)}
						{isDone && markdown && (
							<>
								<Button variant='outline' size='icon' className='cursor-pointer' onClick={handleCopy}>
									<CopyIcon className='size-4' />
								</Button>
								<Button variant='outline' size='icon' className='cursor-pointer' onClick={handleDownload}>
									<DownloadIcon className='size-4' />
								</Button>
							</>
						)}
					</div>
					</div>
					{isDone && markdown && (
						<div className='flex flex-wrap items-center gap-2'>
							<label className='text-xs text-gray-500 dark:text-gray-400' htmlFor='translate-source'>
								Origen
							</label>
							<Select value={sourceLang} onValueChange={setSourceLang} disabled={isTranslating}>
								<SelectTrigger id='translate-source' className='w-36 cursor-pointer bg-white dark:bg-gray-900'>
									<SelectValue placeholder='Origen' />
								</SelectTrigger>
								<SelectContent>
									{languages.map(language => (
										<SelectItem key={language.code} value={language.code}>
											{language.name}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
							<label className='text-xs text-gray-500 dark:text-gray-400' htmlFor='translate-target'>
								Destino
							</label>
							<Select value={targetLang} onValueChange={setTargetLang} disabled={isTranslating}>
								<SelectTrigger id='translate-target' className='w-36 cursor-pointer bg-white dark:bg-gray-900'>
									<SelectValue placeholder='Destino' />
								</SelectTrigger>
								<SelectContent>
									{languages.map(language => (
										<SelectItem key={`target-${language.code}`} value={language.code}>
											{language.name}
										</SelectItem>
									))}
								</SelectContent>
							</Select>
							<Button
								size='sm'
								className='cursor-pointer'
								onClick={handleTranslate}
								disabled={isTranslating}>
								{isTranslating ? 'Traduciendo…' : 'Traducir'}
							</Button>
						</div>
					)}
				</div>

				<div className='flex-1 overflow-hidden'>
					<TabsContent value='markdown' className='h-full m-0 mt-0'>
						{isBusy ? (
							<div className='h-full flex items-center justify-center'>
								<div className='text-center max-w-sm px-4'>
									<div className='inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4'></div>
									<p className='text-gray-500 dark:text-gray-400'>
										{typeof response?.progress === 'number' && response.progress >= 100
											? 'Finalizando…'
											: `Procesando...${typeof response?.progress === 'number' ? ` ${Math.round(response.progress)}%` : ''}`}
									</p>
									{durationLabel && (
										<p className='text-sm text-gray-600 dark:text-gray-300 mt-2 tabular-nums'>
											Tiempo: {durationLabel}
										</p>
									)}
									{formatStep(response?.current_step || response?.current_stage) && (
										<p className='text-xs text-gray-400 dark:text-gray-500 mt-2'>
											{formatStep(response?.current_step || response?.current_stage)}
										</p>
									)}
								</div>
							</div>
						) : isDone && blocks.length > 0 ? (
							<MarkdownPreview />
						) : isDone && markdown ? (
							<div className='h-full overflow-y-auto p-6 markdown-body'>
								<div className='max-w-3xl mx-auto prose dark:prose-invert'>
									<ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeRaw, [rehypeKatex, { throwOnError: false, strict: false }]]}>
										{markdown}
									</ReactMarkdown>
								</div>
							</div>
						) : isDone ? (
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
									<p>No hay contenido Markdown</p>
									<p className='text-xs mt-2'>
										Revisa{' '}
										<code className='text-[11px]'>apps/backend/data/&lt;task_id&gt;/result.md</code>
									</p>
								</div>
							</div>
						) : status === 'failed' ? (
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-red-500 dark:text-red-400'>
									<p>Error al procesar</p>
									{error_message && (
										<p className='text-sm mt-2 text-gray-500 dark:text-gray-400'>{error_message}</p>
									)}
									{durationLabel && (
										<p className='text-xs mt-2 text-gray-500 dark:text-gray-400 tabular-nums'>
											Duró {durationLabel} antes de fallar
										</p>
									)}
								</div>
							</div>
						) : (
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
									<p>Sube un archivo y espera a que termine el procesamiento</p>
								</div>
							</div>
						)}
					</TabsContent>

					<TabsContent value='translation' className='h-full m-0 mt-0'>
						{isTranslating && !translation?.text ? (
							<div className='h-full flex items-center justify-center'>
								<div className='text-center max-w-sm px-4'>
									<div className='inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-4'></div>
									<p className='text-gray-500 dark:text-gray-400'>Traduciendo la transcripción…</p>
								</div>
							</div>
						) : translation?.error && !translation.text ? (
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-red-500 dark:text-red-400 max-w-md'>
									<p>No se pudo traducir</p>
									<p className='text-sm mt-2 text-gray-500 dark:text-gray-400'>{translation.error}</p>
								</div>
							</div>
						) : translation?.text ? (
							<div className='h-full overflow-y-auto p-6 markdown-body'>
								{isTranslating && (
									<p className='max-w-3xl mx-auto mb-3 text-xs text-gray-500 dark:text-gray-400'>
										Actualizando la traducción…
									</p>
								)}
								{translation.error && (
									<p className='max-w-3xl mx-auto mb-3 text-sm text-red-500 dark:text-red-400'>
										{translation.error}
									</p>
								)}
								<div className='max-w-3xl mx-auto prose dark:prose-invert'>
									<ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeRaw, [rehypeKatex, { throwOnError: false, strict: false }]]}>
										{translation.text}
									</ReactMarkdown>
								</div>
							</div>
						) : (
							<div className='h-full flex items-center justify-center'>
								<div className='p-4 rounded-lg text-center text-gray-500 dark:text-gray-400'>
									<p>Elige el idioma de origen y de destino, y pulsa Traducir</p>
								</div>
							</div>
						)}
					</TabsContent>

					<TabsContent value='json' className='h-full m-0 mt-0 overflow-auto'>
						<div className='p-4'>
							{isDone && response ? (
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
