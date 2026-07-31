import { useMemo, useState } from 'react'
import { FileUpload, type TaskResponse, type UploadedFile } from './FileUpload'
import { FilePreview } from './FilePreview'
import { OCRResults } from './OCRResults'

export function OCRPage() {
	const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
	const [taskResponses, setTaskResponses] = useState<Record<string, TaskResponse>>({})
	const [activeFileId, setActiveFileId] = useState<string | null>(null)

	const activeFile = useMemo(
		() => uploadedFiles.find(file => file.id === activeFileId) ?? uploadedFiles[0] ?? null,
		[activeFileId, uploadedFiles]
	)
	const activeResult = activeFile ? taskResponses[activeFile.id] ?? null : null

	const handleFileUploaded = (file: UploadedFile) => {
		setUploadedFiles(files => [...files, file])
		setActiveFileId(current => current ?? file.id)
	}

	const handleTaskStatusChange = (response: TaskResponse) => {
		setTaskResponses(current => ({ ...current, [response.fileId]: response }))
		if (response.status === 'completed' || response.status === 'failed') {
			setActiveFileId(response.fileId)
		}
	}

	return (
		<div className='h-screen flex overflow-hidden bg-gray-50 dark:bg-gray-950'>
			<div className='w-72 shrink-0'>
				<FileUpload
					onFileUploaded={handleFileUploaded}
					onTaskStatusChange={handleTaskStatusChange}
				/>
			</div>

			<main className='h-screen flex-1 min-w-0 grid grid-cols-2 overflow-hidden'>
				<div className='min-w-0 relative'>
					{uploadedFiles.length > 1 && (
						<div className='absolute top-2 left-2 right-2 z-10 flex gap-1 overflow-x-auto rounded-md bg-white/90 dark:bg-gray-900/90 p-1 shadow'>
							{uploadedFiles.map(file => {
								const status = taskResponses[file.id]?.status
								return (
									<button
										key={file.id}
										type='button'
										onClick={() => setActiveFileId(file.id)}
										className={`max-w-44 truncate rounded px-2 py-1 text-xs ${activeFile?.id === file.id ? 'bg-primary text-primary-foreground' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}`}
										title={file.name}>
										{status === 'completed' ? '✓ ' : status === 'failed' ? '× ' : ''}{file.name}
									</button>
								)
							})}
						</div>
					)}
					<FilePreview file={activeFile} result={activeResult} />
				</div>
				<OCRResults result={activeResult} fileName={activeFile?.name} />
			</main>
		</div>
	)
}
