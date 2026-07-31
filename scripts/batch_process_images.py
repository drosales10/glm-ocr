"""
Batch OCR processing script for GLM-OCR

Procesa todas las imágenes de un directorio usando GLM-OCR SDK.

Uso:
    python scripts/batch_process_images.py --input "c:/Users/User/Downloads/GLM-OCR/examples/2. Arboles Cultivados" --output "c:/Users/User/Downloads/GLM-OCR/results"
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import json

# Agregar directorio raíz al path para importar módulos locales
script_dir = Path(__file__).resolve().parent.parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from glmocr import GlmOcr
from glmocr.utils.logging import get_logger

# Configurar logger
logger = get_logger("batch_ocr_processor")


def get_image_files(directory: str, extensions: Optional[List[str]] = None) -> List[Path]:
    """
    Obtener todos los archivos de imagen de un directorio.

    Args:
        directory: Ruta al directorio
        extensions: Lista de extensiones a incluir (por defecto: imágenes comunes)

    Returns:
        Lista de rutas a archivos de imagen
    """
    if extensions is None:
        extensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".gif"]

    dir_path = Path(directory)
    if not dir_path.exists():
        raise ValueError(f"El directorio no existe: {directory}")

    if not dir_path.is_dir():
        raise ValueError(f"La ruta no es un directorio: {directory}")

    image_files = []
    for ext in extensions:
        image_files.extend(dir_path.glob(f"*{ext}"))
        image_files.extend(dir_path.glob(f"*{ext.upper()}"))

    # Eliminar duplicados y ordenar
    image_files = sorted(set(image_files))

    return image_files


def parse_args() -> argparse.Namespace:
    """Parsear argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Batch OCR processing for images using GLM-OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
    python scripts/batch_process_images.py --input "path/to/images"
    python scripts/batch_process_images.py --input "path/to/images" --output "path/to/results"
    python scripts/batch_process_images.py --input "path/to/images" --config "path/to/config.yaml"
    python scripts/batch_process_images.py --input "path/to/images" --start-index 10 --end-index 50
        """
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Directorio de entrada con las imágenes a procesar"
    )

    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Directorio de salida para los resultados (por defecto: input/results)"
    )

    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help="Ruta al archivo de configuración YAML"
    )

    parser.add_argument(
        "--start-index",
        "-s",
        type=int,
        default=0,
        help="Índice inicial para procesamiento (por defecto: 0)"
    )

    parser.add_argument(
        "--end-index",
        "-e",
        type=int,
        default=None,
        help="Índice final para procesamiento (por defecto: todos)"
    )

    parser.add_argument(
        "--retry-count",
        "-r",
        type=int,
        default=3,
        help="Número de reintentos por error (por defecto: 3)"
    )

    parser.add_argument(
        "--retry-delay",
        "-d",
        type=int,
        default=5,
        help="Tiempo de espera entre reintentos en segundos (por defecto: 5)"
    )

    parser.add_argument(
        "--parallel",
        "-p",
        type=int,
        default=1,
        help="Número de imágenes a procesar en paralelo (por defecto: 1)"
    )

    parser.add_argument(
        "--skip-existing",
        "-k",
        action="store_true",
        help="Saltar archivos que ya tienen resultados"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verboso"
    )

    parser.add_argument(
        "--json-only",
        "-j",
        action="store_true",
        help="No guardar las visualizaciones de layout (el Markdown se sigue guardando)"
    )

    parser.add_argument(
        "--layout-device",
        "-l",
        choices=["cpu", "cuda", "mps"],
        default=None,
        help="Dispositivo para layout detection (por defecto: auto)"
    )

    return parser.parse_args()


async def process_single_image(
    processor: GlmOcr,
    image_path: Path,
    output_dir: Path,
    retry_count: int = 3,
    retry_delay: int = 5,
    json_only: bool = False
) -> dict:
    """
    Procesar una sola imagen con reintentos.

    Args:
        processor: Instancia de GlmOcr
        image_path: Ruta a la imagen
        output_dir: Directorio de salida
        retry_count: Número de reintentos
        retry_delay: Tiempo entre reintentos (segundos)
        json_only: Solo generar JSON

    Returns:
        Diccionario con resultados
    """
    result = {
        "image_path": str(image_path),
        "success": False,
        "output_files": {},
        "error": None,
        "attempts": 0
    }

    for attempt in range(1, retry_count + 1):
        result["attempts"] = attempt
        try:
            logger.info(f"Procesando: {image_path.name} (intent {attempt}/{retry_count})")

            # Procesar imagen
            parsed_result = processor.parse(str(image_path))

            # El SDK crea output_dir/<nombre_imagen>/ y guarda allí el JSON/Markdown.
            parsed_result.save(
                output_dir,
                save_layout_visualization=not json_only,
            )

            output_base = output_dir / image_path.stem
            json_file = output_base / f"{image_path.stem}.json"
            md_file = output_base / f"{image_path.stem}.md"

            if json_file.exists():
                result["output_files"]["json"] = str(json_file)
            if not json_only and md_file.exists():
                result["output_files"]["markdown"] = str(md_file)

            # Guardar metadatos adicionales serializables.
            metadata_file = output_base / "metadata.json"
            metadata = {
                "input_image": str(image_path),
                "processing_timestamp": datetime.now().isoformat(),
                "json_result": parsed_result.json_result,
                "markdown_result": parsed_result.markdown_result or "",
            }
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            result["output_files"]["metadata"] = str(metadata_file)
            result["success"] = True
            logger.info(f"Éxito: {image_path.name}")
            break

        except Exception as e:
            result["error"] = str(e)
            logger.error(
                f"Error procesando {image_path.name} (intent {attempt}/{retry_count}): {e}"
            )
            if attempt < retry_count:
                logger.info(f"Esperando {retry_delay}s antes de reintentar...")
                await asyncio.sleep(retry_delay)

    return result


async def process_batch(
    input_dir: str,
    output_dir: str,
    config_path: Optional[str] = None,
    start_index: int = 0,
    end_index: Optional[int] = None,
    retry_count: int = 3,
    retry_delay: int = 5,
    parallel: int = 1,
    skip_existing: bool = False,
    verbose: bool = False,
    json_only: bool = False,
    layout_device: Optional[str] = None
) -> dict:
    """
    Procesar lote de imágenes.

    Args:
        input_dir: Directorio de imágenes
        output_dir: Directorio de salida
        config_path: Ruta al config YAML
        start_index: Índice inicial
        end_index: Índice final
        retry_count: Reintentos por error
        retry_delay: Delay entre reintentos
        parallel: Procesamiento paralelo
        skip_existing: Saltar archivos existentes
        verbose: Modo verboso
        json_only: Solo JSON
        layout_device: Dispositivo para layout

    Returns:
        Diccionario con resumen del procesamiento
    """
    # Configurar logger
    if verbose:
        logger.setLevel("DEBUG")
    else:
        logger.setLevel("INFO")

    # Obtener lista de imágenes
    logger.info(f"Buscando imágenes en: {input_dir}")
    try:
        image_files = get_image_files(input_dir)
        total_images = len(image_files)
        logger.info(f"Encontradas {total_images} imágenes")
    except ValueError as e:
        return {"success": False, "error": str(e), "processed": 0}

    # Filtrar por rango
    image_files = image_files[start_index:end_index]
    images_to_process = len(image_files)
    logger.info(f"Procesando imágenes {start_index} a {end_index}: {images_to_process} imágenes")

    # Crear directorio de salida
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Directorio de salida: {output_path}")

    if retry_count < 1:
        raise ValueError("retry_count debe ser mayor o igual que 1")

    # Inicializar procesador GLM-OCR
    logger.info("Inicializando procesador GLM-OCR...")
    processor = GlmOcr(
        config_path=config_path,
        layout_device=layout_device,
    )

    # Procesar imágenes
    results = []
    successes = 0
    failures = 0
    skipped = 0

    for i, image_path in enumerate(image_files, start=1):
        # Verificar si ya existe resultado
        if skip_existing:
            output_base = output_path / image_path.stem
            json_file = output_base / f"{image_path.stem}.json"
            if json_file.exists():
                logger.info(f"Saltando (ya existe): {image_path.name}")
                skipped += 1
                continue

        # Procesar imagen
        result = await process_single_image(
            processor=processor,
            image_path=image_path,
            output_dir=output_path,
            retry_count=retry_count,
            retry_delay=retry_delay,
            json_only=json_only
        )
        results.append(result)

        if result["success"]:
            successes += 1
        else:
            failures += 1

        # Progreso
        progress = (i / images_to_process) * 100
        logger.info(
            f"Progreso: {i}/{images_to_process} ({progress:.1f}%) "
            f"| Éxitos: {successes} | Fallas: {failures} | Saltados: {skipped}"
        )

    processor.close()

    # Resumen final
    summary = {
        "success": failures == 0,
        "input_directory": input_dir,
        "output_directory": str(output_path),
        "total_images": total_images,
        "images_to_process": images_to_process,
        "processed": successes + failures,
        "successes": successes,
        "failures": failures,
        "skipped": skipped,
        "results": results
    }

    # Guardar resumen
    summary_file = output_path / "processing_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"\n{'='*60}")
    logger.info(f"Procesamiento completado:")
    logger.info(f"  Total imágenes: {total_images}")
    logger.info(f"  Procesadas: {successes + failures}")
    logger.info(f"  Éxitos: {successes}")
    logger.info(f"  Fallas: {failures}")
    logger.info(f"  Saltadas: {skipped}")
    logger.info(f"  Resumen guardado en: {summary_file}")
    logger.info(f"{'='*60}\n")

    return summary


def main():
    """Función principal."""
    args = parse_args()

    # Determinar directorio de salida
    if args.output is None:
        output_dir = Path(args.input) / "results"
    else:
        output_dir = args.output

    # Ejecutar procesamiento
    summary = asyncio.run(process_batch(
        input_dir=args.input,
        output_dir=str(output_dir),
        config_path=args.config,
        start_index=args.start_index,
        end_index=args.end_index,
        retry_count=args.retry_count,
        retry_delay=args.retry_delay,
        parallel=args.parallel,
        skip_existing=args.skip_existing,
        verbose=args.verbose,
        json_only=args.json_only,
        layout_device=args.layout_device
    ))

    # Salir con código adecuado
    if summary["success"]:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()