import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
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
