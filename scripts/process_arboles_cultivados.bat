@echo off
REM Batch script to process Arboles Cultivados images
REM This script runs the Python batch processor on all images in the Arboles Cultivados directory

echo ========================================
echo Processing Arboles Cultivados images
echo ========================================

cd /d "%~dp0.."

echo.
echo Starting batch OCR processing...
echo.

REM Run the batch processor
REM Adjust --retry-count, --retry-delay, and other options as needed
python scripts/batch_process_images.py ^
    --input "c:\Users\User\Downloads\GLM-OCR\examples\2. Arboles Cultivados" ^
    --output "c:\Users\User\Downloads\GLM-OCR\results\arboles_cultivados" ^
    --config "c:\Users\User\Downloads\GLM-OCR\config.yaml" ^
    --retry-count 3 ^
    --retry-delay 5 ^
    --skip-existing ^
    --verbose

echo.
echo ========================================
echo Processing completed!
echo Results saved to: c:\Users\User\Downloads\GLM-OCR\results\arboles_cultivados
echo ========================================

pause
