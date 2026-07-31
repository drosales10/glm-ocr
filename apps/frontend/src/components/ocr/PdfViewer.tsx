// PdfViewerCanvasOnly.tsx
import { ChevronLeft, ChevronRight, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';
import React, { useMemo, useState, useRef, useEffect, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { usePdfNavigation } from '@/hooks/usePdfNavigation';
import { usePdfZoom } from '@/hooks/usePdfZoom';

import 'react-pdf/dist/Page/AnnotationLayer.css';
// import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `https://registry.npmmirror.com/pdfjs-dist/${pdfjs.version}/files/build/pdf.worker.min.mjs`



interface PdfViewerProps {
    file: File | null;
    className?: string;
    renderPageOverlay?: (pageNumber: number) => React.ReactNode;
    onPageClick?: (e: React.MouseEvent<HTMLDivElement>, pageNumber: number) => void;
    onPageMouseMove?: (e: React.MouseEvent<HTMLDivElement>, pageNumber: number) => void;
    onPageMouseLeave?: (e: React.MouseEvent<HTMLDivElement>, pageNumber: number) => void;
}

// Configuración de renderizado virtual
const VIRTUAL_CONFIG = {
    BUFFER_PAGES: 2, // Páginas de búfer a renderizar antes y después del viewport
    PLACEHOLDER_HEIGHT: 842, // Altura predeterminada de página A4 (px); se ajusta dinámicamente según la altura real
};

const PdfViewerCanvasOnly: React.FC<PdfViewerProps> = ({
    file = null,
    className = '',
    renderPageOverlay,
    onPageClick,
    onPageMouseMove,
    onPageMouseLeave,
}) => {
    const [numPages, setNumPages] = useState<number>(0);
    // Estado relacionado con el renderizado virtual
    const [visibleRange, setVisibleRange] = useState<[number, number]>([1, 1]);
    const [pageHeights, setPageHeights] = useState<Record<number, number>>({});
    const [viewportHeight, setViewportHeight] = useState<number>(0);

    const pageRefs = useRef<(HTMLDivElement | null)[]>([]); // ref de cada página
    const scrollContainerRef = useRef<HTMLDivElement | null>(null);
    const resizeObserverRef = useRef<ResizeObserver | null>(null);

    const documentOptions = useMemo(
        () => ({
            cMapUrl: `https://registry.npmmirror.com/pdfjs-dist/${pdfjs.version}/files/cmaps/`,
            cMapPacked: true,
        }),
        []
    );

    // Usar el hook de zoom del PDF
    const { scale, zoomIn, zoomOut, resetZoom, setAutoScale, isInitialScaleSetRef } = usePdfZoom();

    // Calcular la altura acumulada de las páginas (para placeholders), considerando la escala
    const getPageOffset = useCallback((pageNumber: number): number => {
        let offset = 20; // padding del contenedor
        for (let i = 1; i < pageNumber; i++) {
            const pageHeight = (pageHeights[i] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT) * scale;
            offset += pageHeight + 20; // altura de página escalada + espaciado mb-5
        }
        return offset;
    }, [pageHeights, scale]);

    // Usar el hook de navegación del PDF
    const { currentPage, inputValue, setInputValue, setCurrentPage, prevPage, nextPage, isProgrammaticScrollRef, lastProgrammaticPageRef } = usePdfNavigation({ numPages, getPageOffset, scrollContainerRef });

    const onDocumentLoadSuccess = async ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
        setCurrentPage(1);
        setInputValue('1');
        pageRefs.current = new Array(numPages).fill(null); // Inicializar el array de refs

        // Inicializar la altura de las páginas con valores por defecto
        const initialHeights: Record<number, number> = {};
        for (let i = 1; i <= numPages; i++) {
            initialHeights[i] = VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT;
        }
        setPageHeights(initialHeights);

        // Calcular la escala inicial adaptativa
        const container = scrollContainerRef.current;
        if (container && !isInitialScaleSetRef.current) {
            // Esperar un frame para asegurar que el tamaño del contenedor sea correcto
            await new Promise(resolve => requestAnimationFrame(resolve));

            const containerWidth = container.clientWidth - 32; // restar el padding
            const containerHeight = container.clientHeight - 32;

            // Tamaño predeterminado A4: 595 x 842 puntos
            const defaultPageWidth = 595;
            const defaultPageHeight = 842;

            // Calcular la escala por ancho y por alto
            const scaleByWidth = containerWidth / defaultPageWidth;
            const scaleByHeight = containerHeight / defaultPageHeight;

            // Usar la menor escala para asegurar que la página se muestre completa
            const autoScale = Math.min(scaleByWidth, scaleByHeight, 1.5); // máximo 1.5x

            setAutoScale(autoScale);
        }
    };

    // Calcular la altura total, considerando la escala
    const totalHeight = useMemo(() => {
        let height = 0;
        for (let i = 1; i <= numPages; i++) {
            height += (pageHeights[i] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT) * scale;
        }
        // Añadir espaciado entre páginas (la última no necesita margen inferior)
        height += (numPages > 0 ? (numPages - 1) * 20 : 0);
        return height;
    }, [numPages, pageHeights, scale]);

    // Calcular el rango de páginas visibles según la posición de scroll
    const calculateVisibleRange = useCallback(() => {
        if (!scrollContainerRef.current || viewportHeight === 0) {
            return [1, 1];
        }

        const scrollTop = scrollContainerRef.current.scrollTop;
        const { BUFFER_PAGES } = VIRTUAL_CONFIG;

        // Encontrar la primera página parcialmente visible
        let startPage = 1;
        for (let i = 1; i <= numPages; i++) {
            const pageOffset = getPageOffset(i);
            const pageHeight = (pageHeights[i] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT) * scale;
            const pageBottom = pageOffset + pageHeight;

            if (pageBottom > scrollTop) {
                startPage = i;
                break;
            }
        }

        // Encontrar la última página parcialmente visible
        const viewportBottom = scrollTop + viewportHeight;
        let endPage = numPages;
        for (let i = startPage; i <= numPages; i++) {
            const pageOffset = getPageOffset(i);
            const pageHeight = (pageHeights[i] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT) * scale;
            if (pageOffset + pageHeight >= viewportBottom) {
                endPage = i;
                break;
            }
        }

        // Añadir búfer
        startPage = Math.max(1, startPage - BUFFER_PAGES);
        endPage = Math.min(numPages, endPage + BUFFER_PAGES);

        return [startPage, endPage];
    }, [viewportHeight, numPages, pageHeights, scale, getPageOffset]);

    // Actualizar el rango visible
    const updateVisibleRange = useCallback(() => {
        const [start, end] = calculateVisibleRange();
        setVisibleRange([start, end]);
    }, [calculateVisibleRange]);

    // Actualizar la altura cuando la página termine de cargar
    const handlePageRenderSuccess = useCallback((pageNumber: number, pageElement: HTMLDivElement) => {
        // Obtener la altura renderizada real (ya incluye scale); dividir por scale para la altura original
        const renderedHeight = pageElement.offsetHeight;
        const originalHeight = renderedHeight / scale;

        // Actualizar el estado interno (almacenar la altura original)
        setPageHeights(prev => {
            if (prev[pageNumber] !== originalHeight) {
                return { ...prev, [pageNumber]: originalHeight };
            }
            return prev;
        });
    }, [scale]);

    // Escuchar el scroll
    useEffect(() => {
        const handleScroll = () => {
            // Si el scroll es programático, usar directamente la página destino sin recalcular
            if (isProgrammaticScrollRef.current) {
                const targetPage = lastProgrammaticPageRef.current;
                if (targetPage !== currentPage) {
                    setCurrentPage(targetPage);
                    setInputValue(targetPage.toString());
                }
                updateVisibleRange();
                return;
            }

            // Actualizar el número de página actual
            let visiblePage = 1;
            pageRefs.current.forEach((ref, idx) => {
                if (ref) {
                    const rect = ref.getBoundingClientRect();
                    if (rect.top <= 100 && rect.bottom >= 100) {
                        visiblePage = idx + 1;
                    }
                }
            });
            if (visiblePage !== currentPage) {
                setCurrentPage(visiblePage);
                setInputValue(visiblePage.toString());
            }

            // Actualizar el rango visible
            updateVisibleRange();
        };

        const container = scrollContainerRef.current;
        container?.addEventListener('scroll', handleScroll);
        return () => container?.removeEventListener('scroll', handleScroll);
    }, [numPages, currentPage, pageHeights, scale, updateVisibleRange]);

    // Escuchar cambios de tamaño del contenedor
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const updateHeight = () => {
            setViewportHeight(container.clientHeight);
            updateVisibleRange();
        };

        updateHeight();

        resizeObserverRef.current = new ResizeObserver(() => {
            updateHeight();
        });
        resizeObserverRef.current.observe(container);

        return () => {
            resizeObserverRef.current?.disconnect();
            resizeObserverRef.current = null;
        };
    }, [updateVisibleRange]);

    // Escuchar cambios de escala y actualizar el rango visible
    useEffect(() => {
        updateVisibleRange();
    }, [scale, updateVisibleRange]);


    // Renderizar el componente de página
    const renderPage = (pageNumber: number) => {
        const height = pageHeights[pageNumber] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT;

        return (
            <div
                key={`page_${pageNumber}`}
                ref={(el) => {
                    pageRefs.current[pageNumber - 1] = el;
                    if (el) {
                        // Actualizar la altura tras renderizar la página
                        setTimeout(() => handlePageRenderSuccess(pageNumber, el), 0);
                    }
                }}
                className={`relative shadow-md bg-white mb-5 mx-auto`}
                style={{ minHeight: numPages > 1 ? height * scale : 'auto', width: 'fit-content' }}
                data-pdf-page={pageNumber}
                data-pdf-visible
                onClick={onPageClick ? (e) => onPageClick(e, pageNumber) : undefined}
                onMouseMove={onPageMouseMove ? (e) => onPageMouseMove(e, pageNumber) : undefined}
                onMouseLeave={onPageMouseLeave ? (e) => onPageMouseLeave(e, pageNumber) : undefined}
            >
                <Page
                    pageNumber={pageNumber}
                    scale={scale}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    onRenderError={(error) => console.error(`Page ${pageNumber} render error:`, error)}
                />
                {renderPageOverlay ? renderPageOverlay(pageNumber) : null}
            </div>
        );
    };

    // Renderizar placeholder
    const renderPlaceholder = (pageNumber: number) => {
        const height = pageHeights[pageNumber] || VIRTUAL_CONFIG.PLACEHOLDER_HEIGHT;

        return (
            <div
                key={`placeholder_${pageNumber}`}
                data-pdf-page={pageNumber}
                className={`relative w-full mb-5`}
                style={{ minHeight: height * scale }}
            >
            </div>
        );
    };

    const [startPage, endPage] = visibleRange;

    return (
        <div className={`pdf-viewer flex flex-col h-full overflow-hidden ${className}`}>
            {/* Barra de herramientas: zoom + paginación */}
            <div className="toolbar bg-white border-b p-2 grid grid-cols-2 xl:grid-cols-3 gap-4 sticky top-0 z-10">
                <div className='hidden xl:block text-nowrap truncate'>{file?.name || 'Vista previa PDF'}</div>
                <div className="flex items-center justify-center gap-3">

                    <button
                        onClick={prevPage}
                        disabled={currentPage <= 1}
                        className="size-6 cursor-pointer"
                    >
                        <ChevronLeft size={20} strokeWidth={1} />
                    </button>
                    <div className="flex items-center gap-1">

                        <input
                            type="number"
                            min={1}
                            max={numPages}
                            value={inputValue}
                            onChange={(e) => {
                                setInputValue(e.target.value);
                            }}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    e.currentTarget.blur();
                                }
                            }}
                            className="w-12 border rounded-sm text-center"
                        />
                        <span className="text-sm text-gray-500">/</span>
                        <span className="text-sm text-gray-500">{numPages || '?'}</span>
                    </div>

                    <button
                        onClick={nextPage}
                        disabled={currentPage >= numPages}
                        className="size-6 cursor-pointer"
                    >
                        <ChevronRight size={20} strokeWidth={1} />
                    </button>

                </div>

                <div className="flex items-center justify-end gap-3">
                    <button onClick={zoomOut} className="size-6 cursor-pointer">
                        <ZoomOut size={20} strokeWidth={1} />
                    </button>
                    <span className="text-sm text-gray-500 w-10 text-center">{Math.round(scale * 100)}%</span>
                    <button onClick={zoomIn} className="size-6 cursor-pointer">
                        <ZoomIn size={20} strokeWidth={1} />
                    </button>
                    <button onClick={resetZoom} className="size-6 cursor-pointer">
                        <RotateCcw size={18} strokeWidth={1} />
                    </button>
                </div>
            </div>

            {/* Contenedor de scroll - renderizado virtual */}
            <div ref={scrollContainerRef} className="flex-1 overflow-auto bg-gray-50 p-4 pdf-scroll-container relative">
                <Document
                    file={file}
                    options={documentOptions}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={<div className="text-center py-20 text-gray-500">Cargando PDF...</div>}
                    error={<div className="text-red-600 text-center py-20">Error al cargar el PDF. Revisa el archivo</div>}
                >
                    {numPages > 0 && (
                        <div
                            className="relative min-w-full flex flex-col items-center overflow-x-auto overflow-y-hidden"
                            style={{ height: Math.round(totalHeight) }}
                        >
                            {Array.from({ length: numPages }, (_, index) => {
                                const pageNumber = index + 1;
                                if (pageNumber >= startPage && pageNumber <= endPage) {
                                    return renderPage(pageNumber);
                                }
                                return renderPlaceholder(pageNumber);
                            })}
                        </div>
                    )}
                </Document>
            </div>
        </div>
    );
};

export default PdfViewerCanvasOnly;
