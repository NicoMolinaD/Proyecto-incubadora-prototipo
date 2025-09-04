"""
Utilidades compartidas para el sistema de incubadora neonatal
"""
import logging
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
import hashlib
import secrets
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Configura el sistema de logging para la aplicación

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Archivo donde guardar los logs (opcional)

    Returns:
        Logger configurado
    """
    logger = logging.getLogger("incubadora_neonatal")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Limpiar handlers existentes
    logger.handlers.clear()

    # Formato de logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para archivo (si se especifica)
    if log_file:
        # Crear directorio si no existe
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_current_timestamp() -> str:
    """
    Retorna timestamp actual en formato ISO con timezone UTC

    Returns:
        String con timestamp en formato ISO
    """
    return datetime.now(timezone.utc).isoformat()


def validate_sensor_ranges(sensor_data: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Valida que los datos de sensores estén dentro de rangos aceptables

    Args:
        sensor_data: Diccionario con datos de sensores

    Returns:
        Lista de violaciones encontradas
    """
    # Rangos aceptables para sensores (más amplios que los normales para validación básica)
    acceptable_ranges = {
        'temperatura': (30.0, 45.0),  # °C
        'humedad': (0.0, 100.0),  # %
        'oxigeno': (15.0, 100.0),  # %
        'frecuencia_cardiaca': (50, 250),  # bpm
        'frecuencia_respiratoria': (10, 100),  # rpm
        'presion_arterial_sistolica': (30, 150),  # mmHg
        'presion_arterial_diastolica': (15, 100)  # mmHg
    }

    violations = []

    for parameter, value in sensor_data.items():
        if parameter in acceptable_ranges:
            min_val, max_val = acceptable_ranges[parameter]
            if not isinstance(value, (int, float)):
                violations.append({
                    'parameter': parameter,
                    'value': value,
                    'error': 'Invalid data type, expected number',
                    'acceptable_range': [min_val, max_val]
                })
            elif value < min_val or value > max_val:
                violations.append({
                    'parameter': parameter,
                    'value': value,
                    'error': 'Value outside acceptable range',
                    'acceptable_range': [min_val, max_val]
                })

    return violations


def sanitize_filename(filename: str) -> str:
    """
    Sanitiza un nombre de archivo eliminando caracteres peligrosos

    Args:
        filename: Nombre de archivo original

    Returns:
        Nombre de archivo sanitizado
    """
    # Caracteres no permitidos
    invalid_chars = '<>:"/\\|?*'

    # Reemplazar caracteres inválidos
    sanitized = filename
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')

    # Remover espacios al inicio/final
    sanitized = sanitized.strip()

    # Asegurar que no esté vacío
    if not sanitized:
        sanitized = f"file_{get_current_timestamp().replace(':', '-')}"

    return sanitized


def generate_secure_token(length: int = 32) -> str:
    """
    Genera un token seguro aleatorio

    Args:
        length: Longitud del token en bytes

    Returns:
        Token en formato hexadecimal
    """
    return secrets.token_hex(length)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hashea una contraseña de forma segura

    Args:
        password: Contraseña en texto plano
        salt: Salt opcional (se genera uno si no se proporciona)

    Returns:
        Tupla con (hash, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # Usar PBKDF2 para hashear la contraseña
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                              salt.encode('utf-8'), 100000)

    return key.hex(), salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """
    Verifica una contraseña contra su hash

    Args:
        password: Contraseña en texto plano
        hashed_password: Hash de la contraseña
        salt: Salt usado para el hash

    Returns:
        True si la contraseña es correcta
    """
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                              salt.encode('utf-8'), 100000)

    return key.hex() == hashed_password


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """
    Carga JSON de forma segura, retornando un valor por defecto si falla

    Args:
        json_string: String JSON a parsear
        default: Valor por defecto si falla el parsing

    Returns:
        Objeto parseado o valor por defecto
    """
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "null") -> str:
    """
    Serializa objeto a JSON de forma segura

    Args:
        obj: Objeto a serializar
        default: String por defecto si falla la serialización

    Returns:
        String JSON o valor por defecto
    """
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


def get_env_var(var_name: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Obtiene variable de entorno de forma segura

    Args:
        var_name: Nombre de la variable
        default: Valor por defecto
        required: Si es requerida (lanza excepción si no existe)

    Returns:
        Valor de la variable

    Raises:
        ValueError: Si la variable es requerida y no existe
    """
    value = os.getenv(var_name, default)

    if required and value is None:
        raise ValueError(f"Required environment variable '{var_name}' not found")

    return value


def calculate_statistics(data: List[Union[int, float]]) -> Dict[str, float]:
    """
    Calcula estadísticas básicas de una lista de números

    Args:
        data: Lista de números

    Returns:
        Diccionario con estadísticas
    """
    if not data:
        return {
            'count': 0,
            'min': None,
            'max': None,
            'mean': None,
            'median': None
        }

    sorted_data = sorted(data)
    n = len(data)

    # Mediana
    if n % 2 == 0:
        median = (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
    else:
        median = sorted_data[n // 2]

    return {
        'count': n,
        'min': float(min(data)),
        'max': float(max(data)),
        'mean': float(sum(data) / len(data)),
        'median': float(median)
    }


def format_alert_message(alert_level: str, parameter: str, value: float,
                         normal_range: tuple[float, float]) -> str:
    """
    Formatea un mensaje de alerta de forma consistente

    Args:
        alert_level: Nivel de alerta
        parameter: Parámetro afectado
        value: Valor actual
        normal_range: Rango normal (min, max)

    Returns:
        Mensaje formateado
    """
    min_val, max_val = normal_range

    if value < min_val:
        status = "BAJO"
        deviation = min_val - value
    else:
        status = "ALTO"
        deviation = value - max_val

    return (f"ALERTA {alert_level}: {parameter.upper()} {status} - "
            f"Valor: {value:.2f}, Rango normal: {min_val}-{max_val}, "
            f"Desviación: {deviation:.2f}")


def chunk_list(data: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Divide una lista en chunks de tamaño específico

    Args:
        data: Lista a dividir
        chunk_size: Tamaño de cada chunk

    Returns:
        Lista de chunks
    """
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def retry_operation(operation, max_retries: int = 3, delay: float = 1.0):
    """
    Ejecuta una operación con reintentos en caso de error

    Args:
        operation: Función a ejecutar
        max_retries: Número máximo de reintentos
        delay: Delay entre reintentos en segundos

    Returns:
        Resultado de la operación

    Raises:
        Exception: La última excepción si todos los reintentos fallan
    """
    import time

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logging.warning(f"Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(delay)
            else:
                logging.error(f"Operation failed after {max_retries + 1} attempts: {e}")

    raise last_exception


class ConfigManager:
    """
    Gestor de configuración para la aplicación
    """

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config.json"
        self._config = {}
        self.load_config()

    def load_config(self) -> None:
        """Carga configuración desde archivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
        except Exception as e:
            logging.warning(f"Error loading config file {self.config_file}: {e}")
            self._config = {}

    def save_config(self) -> bool:
        """Guarda configuración a archivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"Error saving config file {self.config_file}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene valor de configuración"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Establece valor de configuración"""
        self._config[key] = value

    def get_nested(self, path: str, default: Any = None, separator: str = '.') -> Any:
        """
        Obtiene valor anidado usando notación de puntos
        Ejemplo: get_nested('database.host')
        """
        keys = path.split(separator)
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default


# Instancia global del gestor de configuración
config = ConfigManager()