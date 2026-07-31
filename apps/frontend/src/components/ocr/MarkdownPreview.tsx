// src/components/MarkdownPreview.tsx

'use client'

import { useRef, useMemo, useCallback, useState, useEffect } from 'react'
import { useOcrStore } from '@/store/useOcrStore'
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import './markdown.css'
import rehypeMathInHtml from '@/libs/rehypeMathInHtml'
import { useMdVirtualRendering } from '@/hooks/useMdVirtualRendering'
import { CopyButton } from './CopyButton'

// Configuración de renderizado virtual
const VIRTUAL_CONFIG = {
	BUFFER_BLOCKS: 10, // Bloques de búfer a renderizar antes y después del área visible
	PLACEHOLDER_HEIGHT: 100, // Altura predeterminada del bloque (px)
	DEFAULT_BLOCK_HEIGHT: 150, // Altura predeterminada del bloque
};

// Configuración de KaTeX: desactivar advertencias del modo estricto
const katexOptions = {
	throwOnError: false, // No lanzar error; renderizar como texto
	strict: false, // Desactivar comprobaciones del modo estricto
}

export function MarkdownPreview() {
	const { blocks, hoveredBlockId, clickedPdfBlockId, setHoveredBlockId, setClickedBlockId } = useOcrStore()

	const [showCopyButton, setShowCopyButton] = useState(false)

	const markdownRef = useRef<HTMLDivElement>(null)

	// Usar el hook de renderizado virtual
	const {
		visibleRange,
		itemHeights: blockHeights,
		totalHeight,
		getItemOffset,
		updateVisibleRange,
		handleItemRenderSuccess: handleBlockRenderSuccess
	} = useMdVirtualRendering({
		containerRef: markdownRef,
		totalItems: blocks.length,
		config: {
			bufferSize: VIRTUAL_CONFIG.BUFFER_BLOCKS,
			defaultItemHeight: VIRTUAL_CONFIG.DEFAULT_BLOCK_HEIGHT,
			itemGap: 8, // my-2 = 8px
			startIndex: 0
		}
	})

	// Lógica de scroll: al cambiar clickedPdfBlockId, desplazarse automáticamente al elemento correspondiente
	useEffect(() => {

		const container = markdownRef.current
		if (!clickedPdfBlockId || !container || !getItemOffset) return

		// Encontrar el índice del block destino
		const targetIndex = blocks.findIndex(block => String(block.id) === String(clickedPdfBlockId))
		if (targetIndex === -1) return

		// Calcular el desplazamiento del elemento destino
		const itemOffset = getItemOffset(targetIndex)

		// Obtener la altura del elemento (altura real o predeterminada)
		const itemHeight = (blockHeights[targetIndex] || VIRTUAL_CONFIG.DEFAULT_BLOCK_HEIGHT)

		// Calcular la posición de scroll destino: centrar el elemento
		// Fórmula: itemOffset - (altura del contenedor / 2) + (altura del elemento / 2)
		const containerHeight = container.clientHeight
		const padding = 24
		const targetScrollTop = itemOffset - containerHeight / 2 + itemHeight / 2

		// Actualizar primero el rango visible para asegurar que el elemento destino se renderice
		updateVisibleRange?.()

		// Usar requestAnimationFrame para hacer scroll tras actualizar el DOM
		requestAnimationFrame(() => {
			container.scrollTo({
				top: Math.max(0, targetScrollTop - padding),
				// behavior: 'smooth'
			})
		})
	}, [
		clickedPdfBlockId,
		blocks,
		getItemOffset,
		blockHeights,
		updateVisibleRange
	])

	// Manejador de errores de imagen: cachear con useCallback para no recrearlo en cada render
	const handleImageError = useCallback((e: React.SyntheticEvent<HTMLImageElement, Event>) => {
		const target = e.target as HTMLImageElement
		// Si ya es la imagen por defecto, no reemplazar para evitar un bucle infinito
		if (target.dataset.fallback === 'true') {
			return
		}
		target.style.display = 'none'
	}, [])

	// Cachear el objeto components con useMemo para no recrearlo en cada render
	// Debe llamarse antes de cualquier return temprano, cumpliendo las reglas de React Hooks
	const markdownComponents = useMemo(
		() => ({
			img: ({ src, alt, width, height, ...props }: any) => {
				return (
					<img
						src={src}
						alt={alt || 'Imagen'}
						className='max-w-full h-auto rounded-lg my-4 mx-auto block'
						style={{
							width: 'auto',
							height: 'auto',
							maxWidth: '100%'
						}}
						{...props}
						onError={handleImageError}
					/>
				)
			},
			div: ({ children, style, className, ...props }: any) => {
				// Procesar divs que contienen imágenes; asegurar que estilos y className se apliquen correctamente
				return (
					<div style={style} className={className} {...props}>
						{children}
					</div>
				)
			}
		}),
		[handleImageError]
	)


	if (!blocks || blocks.length === 0) {
		return (
			<div className='flex items-center justify-center h-full text-muted-foreground'>
				<p>Sin contenido para mostrar</p>
			</div>
		)
	}


	return (
		<div ref={markdownRef} className='h-full overflow-y-auto p-6 markdown-body'>
			<div
				className='max-w-3xl mx-auto relative'
				style={{ height: totalHeight }}
			>
				{blocks.map((block, index) => {
					if (!block.id) return null

					const [startIndex, endIndex] = visibleRange
					const isInRange = index >= startIndex && index <= endIndex

					const isHovered = hoveredBlockId === block.id
					const isSelected = clickedPdfBlockId === block.id
					const isActive = isHovered || isSelected

					// Determinar si es un bloque de imagen
					const isImage = block.isImage || false

					// Si no está en el rango visible, renderizar un placeholder
					if (!isInRange) {
						const height = blockHeights[index] || VIRTUAL_CONFIG.DEFAULT_BLOCK_HEIGHT
						return (
							<div
								key={block.id}
								data-block-id={block.id}
								className={`px-2 my-2! relative ${isActive ? 'bg-yellow-200/80 dark:bg-yellow-900/70' : 'bg-gray-50/50'}`}
								style={{ minHeight: height }}
							/>
						)
					}

					// Renderizar el bloque real
					return (
						<div
							key={block.id}
							ref={(el) => {
								if (el) {
									// Actualizar la altura tras renderizar el bloque
									setTimeout(() => handleBlockRenderSuccess(index, el), 0)
								}
							}}
							data-block-id={block.id}
							className={`
								px-2 my-2! transition-all duration-300 relative
								${isActive ? 'bg-yellow-200/80 dark:bg-yellow-900/70 shadow-md' : 'bg-card'}
								${isImage ? 'cursor-default' : 'cursor-pointer'}
							`}
							onMouseEnter={() => {
								setHoveredBlockId(block.id)
								setShowCopyButton(true)
							}}
							onMouseLeave={() => {
								setHoveredBlockId(null)
								// setPageNumber(null)
								setShowCopyButton(false)
							}}
							onClick={() => {
								setClickedBlockId(block.id)
								setShowCopyButton(true)
							}}>
							<div className='prose prose-sm dark:prose-invert max-w-none'>
								<ReactMarkdown
									remarkPlugins={[remarkMath]}
									rehypePlugins={[rehypeRaw, rehypeMathInHtml, [rehypeKatex, katexOptions]]}
									components={markdownComponents}>
									{block.content}
								</ReactMarkdown>
							</div>
							{showCopyButton && isActive && (
								<CopyButton content={block.content} />
							)}
						</div>
					)
				})}
			</div>
		</div>
	)
}
