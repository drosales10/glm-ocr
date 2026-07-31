"""
Módulo de encapsulación de logs
Soporta extraer automáticamente el request id del header de la solicitud e imprimirlo
"""

import contextvars
import logging
from contextlib import contextmanager
from typing import Optional

from fastapi import Request

# Definir variables de contexto
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)


class RequestContextFilter(logging.Filter):
    """Filtro de logs para añadir automáticamente request_id a los registros"""

    def set_context(self, request_id: Optional[str] = None):
        """Establece el request_id del contexto actual"""
        if request_id is not None:
            _request_id_var.set(request_id)

    def set_request_id(self, request_id: Optional[str]):
        """Establece el request_id del contexto actual"""
        if request_id is not None:
            _request_id_var.set(request_id)

    def get_request_id(self) -> Optional[str]:
        """Obtiene el request_id del contexto actual"""
        return _request_id_var.get()

    def clear_context(self):
        """Borra el request_id del contexto actual"""
        # Usar set_token para borrar la variable
        _request_id_var.set(None)

    def clear_request_id(self):
        """Borra el request_id del contexto actual"""
        _request_id_var.set(None)

    def filter(self, record):
        """Añade el campo request_id al registro de log"""
        request_id = self.get_request_id()

        record.request_id = request_id if request_id else "N/A"
        return True


# Instancia global del filtro de contexto de solicitud
_context_filter = RequestContextFilter()


class Logger:
    """Clase de encapsulación de logs"""

    def __init__(self, name: str | None = None):
        self.logger = logging.getLogger(name or __name__)
        self._setup_logger()

    def _setup_logger(self):
        """Configura el formato de los logs"""
        # Evitar añadir el manejador más de una vez
        if self.logger.handlers:
            return

        # Crear el manejador
        handler = logging.StreamHandler()

        # Configurar el formato de log, incluyendo request_id y número de línea (subir un nivel)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [request_id:%(request_id)s] - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Añadir el filtro de contexto
        self.logger.addFilter(_context_filter)

        # Establecer el nivel de log
        self.logger.setLevel(logging.DEBUG)

        # Evitar que los logs se propaguen al logger raíz (salida duplicada)
        self.logger.propagate = False

    def debug(self, message: str, *args, **kwargs):
        """Log de depuración"""
        self.logger.debug(message, *args, **kwargs, stacklevel=2)

    def info(self, message: str, *args, **kwargs):
        """Log informativo"""
        self.logger.info(message, *args, **kwargs, stacklevel=2)

    def warning(self, message: str, *args, **kwargs):
        """Log de advertencia"""
        self.logger.warning(message, *args, **kwargs, stacklevel=2)

    def error(self, message: str, *args, **kwargs):
        """Log de error"""
        self.logger.error(message, *args, **kwargs, stacklevel=2)

    def exception(self, message: str, *args, **kwargs):
        """Log de excepción"""
        self.logger.exception(message, *args, **kwargs, stacklevel=2)


def extract_request_id(
    request: Request, header_name: str = "X-Request-ID"
) -> Optional[str]:
    """
    Extrae el request_id del header de la solicitud

    Args:
        request: Objeto de solicitud de Starlette
        header_name: Nombre del header; por defecto 'X-Request-ID'

    Returns:
        Cadena request_id o None
    """
    return request.headers.get(header_name) or request.headers.get("requestid")


@contextmanager
def request_context(
    request: Request,
    request_header_name: str = "X-Request-ID",
):
    """
    Gestor de contexto de solicitud; configura y limpia request_id automáticamente

    Args:
        request: Objeto de solicitud de Starlette
        request_header_name: Nombre del header de request_id; por defecto 'X-Request-ID'
    """
    request_id = extract_request_id(request, request_header_name)

    _context_filter.set_context(
        request_id=request_id,
    )
    try:
        yield
    finally:
        _context_filter.clear_context()


def set_request_id(request_id: str):
    """
    Establece el request_id manualmente

    Args:
        request_id: Cadena request_id
    """
    _context_filter.set_request_id(request_id)


def get_request_id() -> Optional[str]:
    """
    Obtiene el request_id del contexto actual

    Returns:
        Cadena request_id o None
    """
    return _context_filter.get_request_id()


def set_context(request_id: str | None = None):
    """
    Establece el request_id manualmente

    Args:
        request_id: Cadena request_id
    """
    _context_filter.set_context(request_id=request_id)


def clear_request_id():
    """Borra el request_id del hilo actual"""
    _context_filter.clear_request_id()


def clear_context():
    """Borra el contexto del hilo actual (request_id)"""
    _context_filter.clear_context()


# Instancia conveniente de logger
logger = Logger()
