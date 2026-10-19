import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Formatea segundos a una cadena legible en español (p. ej. "2 min 15 s"). */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60

  if (hours > 0) {
    return minutes > 0 ? `${hours} h ${minutes} min ${secs} s` : `${hours} h ${secs} s`
  }
  if (minutes > 0) {
    return secs > 0 ? `${minutes} min ${secs} s` : `${minutes} min`
  }
  return `${secs} s`
}

/** Parsea timestamps del backend; si no traen zona, se asumen UTC. */
export function parseUtcMs(raw?: string | null): number | null {
  if (!raw) return null
  const trimmed = String(raw).trim()
  if (!trimmed) return null
  const hasTz = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)
  const normalized = hasTz
    ? trimmed
    : `${trimmed.replace(' ', 'T')}${trimmed.includes('T') || trimmed.includes(' ') ? 'Z' : ''}`
  const ms = Date.parse(normalized.includes('T') ? normalized : trimmed)
  return Number.isFinite(ms) ? ms : null
}

/** Duración OCR en segundos a partir de execution_time o timestamps. */
export function getOcrDurationSeconds(data: {
  execution_time?: number | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
}, nowMs: number = Date.now()): number | null {
  if (typeof data.execution_time === 'number' && Number.isFinite(data.execution_time) && data.execution_time > 0) {
    return data.execution_time
  }

  const start = parseUtcMs(data.started_at || data.created_at)
  if (start == null) return null

  const end = parseUtcMs(data.completed_at) ?? nowMs
  if (end < start) return 0
  return (end - start) / 1000
}


// Función de copia (JS/TS puro; usable en cualquier proyecto React/Next.js)
export function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return Promise.resolve(false)
  // Priorizar la Clipboard API moderna (solo válida en HTTPS)
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard
      .writeText(text)
      .then(() => true)
      .catch(() => fallbackCopy(text));
  }

  // En HTTP o sin soporte de clipboard API, usar el método clásico de respaldo
  return fallbackCopy(text);
}

// Método clásico de respaldo: crear un textarea oculto + execCommand
function fallbackCopy(text: string): Promise<boolean> {
  return new Promise((resolve) => {
    const textArea = document.createElement('textarea');
    
    // Evitar saltos de scroll y la aparición del teclado en móvil
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.opacity = '0';
    textArea.style.pointerEvents = 'none'; // Evitar interferir con clics
    
    // Necesario para compatibilidad con iOS
    textArea.setAttribute('readonly', 'true');
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
      const successful = document.execCommand('copy');
      resolve(successful);
    } catch (err) {
      console.error('Error al copiar:', err);
      resolve(false);
    } finally {
      document.body.removeChild(textArea);
    }
  });
}
