"""
Clases de excepción de convertidores
"""


class ConverterError(Exception):
    """Excepción base de convertidores"""

    pass


class ConverterValidationError(ConverterError):
    """Excepción de validación de archivo fallida"""

    pass


class ConversionTimeoutError(ConverterError):
    """Excepción de tiempo de espera de conversión"""

    pass


class ConversionFailedError(ConverterError):
    """Excepción de conversión fallida"""

    pass


class UnsupportedFormatError(ConverterError):
    """Excepción de formato de archivo no admitido"""

    pass
