## GLM-OCR

[English](https://github.com/zai-org/GLM-OCR/blob/main/README.md) · [中文](README_zh.md)

<div align="center">
<img src=resources/logo.svg width="40%"/>
</div>
<p align="center">
    👋 Únete a la comunidad en <a href="resources/WECHAT.md" target="_blank">WeChat</a> y <a href="https://discord.gg/QR7SARHRxK" target="_blank">Discord</a>
    <br>
    📖 Informe técnico de GLM-OCR: <a href="https://arxiv.org/abs/2603.10910" target="_blank">arXiv</a>
    <br>
    📍 API oficial: <a href="https://docs.z.ai/guides/vlm/glm-ocr" target="_blank">docs.z.ai</a>
</p>

### Introducción del modelo

GLM-OCR es un modelo OCR multimodal para comprensión de documentos complejos, basado en la arquitectura encoder–decoder GLM-V. Incorpora pérdida Multi-Token Prediction (MTP) y aprendizaje por refuerzo estable multi-tarea para mejorar eficiencia de entrenamiento, precisión y generalización. Integra el encoder visual CogViT, un conector cross-modal ligero con downsampling de tokens, y un decodificador de lenguaje GLM-0.5B. Combinado con el pipeline de dos etapas (análisis de layout + reconocimiento paralelo) basado en PP-DocLayout-V3, ofrece OCR robusto en layouts diversos.

**Características principales**

- **Rendimiento de referencia**: 94.62 en OmniDocBench V1.5 (#1 global); resultados SOTA en fórmulas, tablas y extracción de información.
- **Orientado a escenarios reales**: tablas complejas, documentos con código, sellos y layouts difíciles.
- **Inferencia eficiente**: ~0.9B parámetros; despliegue con vLLM, SGLang y Ollama.
- **Fácil de usar**: SDK open source, CLI y toolchain completa.

### Noticias

- **[2026.3.12]** SDK con modo Skill para agentes — `pip install glmocr` + API key. Ver: [GLM-OCR Skill](skills/glmocr/SKILL.md)
- **[2026.3.12]** Informe técnico disponible: [arXiv](https://arxiv.org/abs/2603.10910)
- **[2026.2.12]** Guía de fine-tuning con LLaMA-Factory: [examples/finetune](examples/finetune/README.md)

### Descargar el modelo

| Modelo  | Enlaces                                                                                                                     | Precisión |
| ------- | --------------------------------------------------------------------------------------------------------------------------- | --------- |
| GLM-OCR | [🤗 Hugging Face](https://huggingface.co/zai-org/GLM-OCR)<br> [🤖 ModelScope](https://modelscope.cn/models/ZhipuAI/GLM-OCR) | BF16      |

---

## Mejoras de este repositorio (despliegue local)

Este fork/adaptación está orientado a **despliegue 100 % local** (sin depender de la nube MaaS). Incluye:

| Mejora | Descripción |
| ------ | ----------- |
| **UI en español** | Frontend y mensajes del backend traducidos al español (incl. modo oscuro). |
| **Cola de carga múltiple** | Subida de varios archivos/carpeta con hasta 3 concurrentes y barra de progreso por archivo. |
| **Progreso de tarea** | Muestra `%` y paso actual (`current_step`) durante el OCR. |
| **Timeouts ampliados** | Frontend 10 min; cliente OCR backend 10 min (evita el error `timeout of 60000ms exceeded`). |
| **CUDA / GPU** | Layout en `cuda` + OCR vía Ollama en GPU (probado en RTX 5050 8 GB). |
| **Config local** | `config.yaml` (Ollama+GPU) y `config.ollama.yaml` de respaldo. |
| **Scripts Windows** | `scripts/start-vllm.ps1` (vLLM + MSVC/cl.exe para RTX 50), lote de imágenes, etc. |
| **Apps web** | Frontend React (`:3006`) + Backend FastAPI (`:8000`) + servidor SDK (`:5002`). |

### Arquitectura local

```
[Frontend :3006]  →  [Backend FastAPI :8000]  →  [glmocr.server :5002]
                                                      │
                         layout (PP-DocLayout, CUDA/CPU) + OCR API
                                                      │
                              [Ollama :11434]  o  [vLLM :8080]
```

### Arranque rápido (Windows)

**Requisitos:** Python ≥ 3.12, Node ≥ 18, pnpm ≥ 8, [Ollama](https://ollama.com) con `glm-ocr:latest`, GPU NVIDIA recomendada.

```powershell
# 1) Modelo OCR en Ollama
ollama pull glm-ocr:latest
# ollama serve  (si no está como servicio)

# 2) SDK + servidor de pipeline
cd C:\ruta\GLM-OCR
.\.venv\Scripts\activate   # o: uv venv --python 3.12 --seed
uv pip install -e ".[selfhosted,server]"
python -m glmocr.server --config config.yaml
# → http://127.0.0.1:5002/glmocr/parse  (solo POST)
# → http://127.0.0.1:5002/health

# 3) Backend de tareas
cd apps\backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# → http://localhost:8000/docs

# 4) Frontend
cd apps\frontend
pnpm install
pnpm dev
# → http://localhost:3006
```

### Configuración GPU (`config.yaml`)

```yaml
pipeline:
  maas:
    enabled: false
  ocr_api:
    api_host: localhost
    api_port: 11434
    api_path: /api/generate
    model: glm-ocr:latest
    api_mode: ollama_generate
    request_timeout: 600
  max_workers: 2
  layout:
    model_dir: PaddlePaddle/PP-DocLayoutV3_safetensors
    device: cuda   # si hay OOM de VRAM, usar: cpu
    batch_size: 1
```

**Notas de rendimiento**

- Una página densa puede tardar **1–5 minutos** (layout + OCR por región). Es esperado.
- Con **1 archivo**, la barra de lote permanece en 0 % hasta terminar; el progreso real está en cada ítem / panel derecho.
- `/glmocr/parse` en el navegador (GET) responde **405 Method Not Allowed** — es normal; solo acepta POST.
- **vLLM (opcional, más throughput):**

```powershell
.\scripts\start-vllm.ps1
# Luego apuntar config a api_port: 8080, api_mode: openai, model: glm-ocr
```

En RTX 50 (sm_120) hace falta **VS Build Tools** (`cl.exe`) para compilar FlashInfer; el script lo añade al PATH si está instalado.

### URLs útiles

| Servicio | URL |
| -------- | --- |
| Interfaz OCR | http://localhost:3006 |
| API Backend / docs | http://localhost:8000/docs |
| Health OCR SDK | http://127.0.0.1:5002/health |
| Ollama | http://127.0.0.1:11434 |

---

## SDK GLM-OCR

### Instalación

```bash
# Nube / MaaS + imágenes/PDF locales
pip install glmocr

# Pipeline self-hosted (layout)
pip install "glmocr[selfhosted]"

# Servicio Flask
pip install "glmocr[server]"
```

Desde código fuente:

```bash
git clone https://github.com/drosales10/glm-ocr.git
cd glm-ocr
uv venv --python 3.12 --seed && source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
```

### Despliegue del modelo

#### Opción 1: API MaaS de Zhipu (inicio rápido en la nube)

Sin GPU local. Obtén una API key en https://open.bigmodel.cn y configura:

```yaml
pipeline:
  maas:
    enabled: true
    api_key: tu-api-key
```

Documentación: https://docs.bigmodel.cn/cn/guide/models/vlm/glm-ocr

#### Opción 2: Self-host con vLLM / SGLang

```bash
pip install "glmocr[selfhosted]"
pip install -U "vllm>=0.19.0"
pip install "transformers>=5.3.0"

vllm serve zai-org/GLM-OCR --port 8080 \
  --speculative-config '{"method": "mtp", "num_speculative_tokens": 3}' \
  --served-model-name glm-ocr
```

Ajusta `--max-model-len` y `--gpu-memory-utilization` según tu hardware.

**SGLang:**

```bash
SGLANG_ENABLE_SPEC_V2=1 sglang serve --model-path zai-org/GLM-OCR --port 8080 \
  --speculative-algorithm NEXTN --speculative-num-steps 3 \
  --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 \
  --served-model-name glm-ocr
```

#### Opción 3: Ollama / MLX

- **[Apple Silicon con mlx-vlm](examples/mlx-deploy/README.md)**
- **[Despliegue con Ollama](examples/ollama-deploy/README.md)**

En este repo, Ollama + `config.yaml` es la vía recomendada en Windows con GPU.

#### Opción 4: Servidor SDK + cliente sin GPU

```yaml
pipeline:
  maas:
    enabled: true
    api_url: http://<IP_SERVIDOR>:5002/glmocr/parse
    api_key: cualquier-cadena
    verify_ssl: false
```

Guía completa: **[Self-hosted SDK Server + Client](examples/self-host/README.md)**

#### Configuración tras levantar el servicio OCR

```yaml
pipeline:
  maas:
    enabled: false
  ocr_api:
    api_host: localhost
    api_port: 8080   # vLLM/SGLang; o 11434 con Ollama
```

### Guía de uso del SDK

#### CLI

```bash
glmocr parse examples/source/code.png
glmocr parse examples/source/
glmocr parse examples/source/code.png --output ./results/
glmocr parse examples/source/code.png --config config.yaml
glmocr parse examples/source/code.png --log-level DEBUG
glmocr parse examples/source/code.png --layout-device cpu
glmocr parse examples/source/code.png --layout-device cuda:0
glmocr parse examples/source/code.png --set pipeline.ocr_api.api_port 8080
```

#### API Python

```python
from glmocr import GlmOcr, parse

result = parse("image.png")
result.save(output_dir="./results")

with GlmOcr() as parser:
    result = parser.parse("image.png")
    print(result.json_result)

with GlmOcr(layout_device="cpu") as parser:
    result = parser.parse("image.png")
```

#### Servicio Flask

```bash
pip install "glmocr[server]"
python -m glmocr.server --config config.yaml

curl -X POST http://localhost:5002/glmocr/parse \
  -H "Content-Type: application/json" \
  -d '{"images": ["./examples/source/code.png"]}'
```

- `images` puede ser string o lista (páginas de un mismo documento).
- Para varios documentos independientes, llama al endpoint una vez por documento.

### Arquitectura modular

| Componente            | Descripción                         |
| --------------------- | ----------------------------------- |
| `PageLoader`          | Preprocesado y codificación         |
| `OCRClient`           | Llamadas al servicio del modelo     |
| `PPDocLayoutDetector` | Detección de layout PP-DocLayout    |
| `ResultFormatter`     | Postprocesado JSON / Markdown       |

```python
from glmocr.dataloader import PageLoader
from glmocr.ocr_client import OCRClient
from glmocr.postprocess import ResultFormatter

class MyPipeline:
  def __init__(self, config):
    self.page_loader = PageLoader(config)
    self.ocr_client = OCRClient(config)
    self.formatter = ResultFormatter(config)

  def process(self, request_data):
    pass
```

## Historial de estrellas

<a href="https://www.star-history.com/?repos=zai-org%2FGLM-OCR&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=zai-org/GLM-OCR&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=zai-org/GLM-OCR&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/image?repos=zai-org/GLM-OCR&type=date&legend=top-left" />
 </picture>
</a>

## Agradecimientos

Proyecto inspirado en:

- [PP-DocLayout-V3](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [MinerU](https://github.com/opendatalab/MinerU)

Upstream original: [zai-org/GLM-OCR](https://github.com/zai-org/GLM-OCR)

## Licencia

El código de este repositorio está bajo Apache License 2.0.

El modelo GLM-OCR se publica bajo MIT License.

El pipeline integra [PP-DocLayoutV3](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3) (Apache 2.0). Cumple ambas licencias al usar el proyecto.

## Cita

```bibtex
@misc{duan2026glmocrtechnicalreport,
      title={GLM-OCR Technical Report},
      author={Shuaiqi Duan and Yadong Xue and Weihan Wang and Zhe Su and Huan Liu and Sheng Yang and Guobing Gan and Guo Wang and Zihan Wang and Shengdong Yan and Dexin Jin and Yuxuan Zhang and Guohong Wen and Yanfeng Wang and Yutao Zhang and Xiaohan Zhang and Wenyi Hong and Yukuo Cen and Da Yin and Bin Chen and Wenmeng Yu and Xiaotao Gu and Jie Tang},
      year={2026},
      eprint={2603.10910},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2603.10910},
}
```
