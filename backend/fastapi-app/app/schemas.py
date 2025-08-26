"""
Esquemas Pydantic para validación y serialización de datos
"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


# Enums para validación
class UserRole(str, Enum):
    admin = "admin"
    doctor = "doctor"
    nurse = "nurse"
    technician = "technician"


class IncubadoraEstado(str, Enum):
    activa = "activa"
    inactiva = "inactiva"
    mantenimiento = "mantenimiento"


class PacienteEstado(str, Enum):
    activo = "activo"
    egresado = "egresado"
    transferido = "transferido"


class AlertaSeveridad(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class AlertaEstado(str, Enum):
    activa = "activa"
    reconocida = "reconocida"
    resuelta = "resuelta"


# Esquemas base
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.nurse
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class User(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Incubadora
class IncubadoraBase(BaseModel):
    codigo: str = Field(..., min_length=3, max_length=20)
    modelo: Optional[str] = Field(None, max_length=50)
    ubicacion: Optional[str] = Field(None, max_length=100)
    estado: IncubadoraEstado = IncubadoraEstado.activa


class IncubadoraCreate(IncubadoraBase):
    fecha_instalacion: Optional[datetime] = None


class IncubadoraUpdate(BaseModel):
    codigo: Optional[str] = Field(None, min_length=3, max_length=20)
    modelo: Optional[str] = Field(None, max_length=50)
    ubicacion: Optional[str] = Field(None, max_length=100)
    estado: Optional[IncubadoraEstado] = None
    ultimo_mantenimiento: Optional[datetime] = None


class Incubadora(IncubadoraBase):
    id: uuid.UUID
    fecha_instalacion: Optional[datetime]
    ultimo_mantenimiento: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Paciente
class PacienteBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    apellidos: str = Field(..., min_length=2, max_length=100)
    fecha_nacimiento: datetime
    peso_nacimiento: Optional[float] = Field(None, ge=0, le=10000)  # gramos
    semanas_gestacion: Optional[int] = Field(None, ge=20, le=50)
    sexo: Optional[str] = Field(None, regex=r'^[MF]$')
    identificacion_madre: Optional[str] = Field(None, max_length=50)


class PacienteCreate(PacienteBase):
    medico_asignado: Optional[uuid.UUID] = None
    incubadora_id: Optional[uuid.UUID] = None


class PacienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    apellidos: Optional[str] = Field(None, min_length=2, max_length=100)
    peso_nacimiento: Optional[float] = Field(None, ge=0, le=10000)
    semanas_gestacion: Optional[int] = Field(None, ge=20, le=50)
    medico_asignado: Optional[uuid.UUID] = None
    incubadora_id: Optional[uuid.UUID] = None
    fecha_egreso: Optional[datetime] = None
    estado: Optional[PacienteEstado] = None


class Paciente(PacienteBase):
    id: uuid.UUID
    medico_asignado: Optional[uuid.UUID]
    incubadora_id: Optional[uuid.UUID]
    fecha_ingreso: datetime
    fecha_egreso: Optional[datetime]
    estado: PacienteEstado
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Datos de Sensores
class SensorDataBase(BaseModel):
    # Variables fisiológicas críticas
    temperatura_corporal: Optional[float] = Field(None, ge=30.0, le=42.0)
    frecuencia_cardiaca: Optional[int] = Field(None, ge=0, le=300)
    frecuencia_respiratoria: Optional[int] = Field(None, ge=0, le=100)
    saturacion_oxigeno: Optional[float] = Field(None, ge=0.0, le=100.0)
    presion_arterial_sistolica: Optional[int] = Field(None, ge=0, le=200)
    presion_arterial_diastolica: Optional[int] = Field(None, ge=0, le=150)

    # Variables ambientales de la incubadora
    temperatura_incubadora: Optional[float] = Field(None, ge=20.0, le=40.0)
    humedad_incubadora: Optional[float] = Field(None, ge=0.0, le=100.0)
    concentracion_oxigeno: Optional[float] = Field(None, ge=15.0, le=100.0)
    presion_aire: Optional[float] = Field(None, ge=90000.0, le=110000.0)  # Pa
    nivel_ruido: Optional[float] = Field(None, ge=0.0, le=120.0)  # dB

    # Variables adicionales
    peso_actual: Optional[float] = Field(None, ge=0.0, le=10000.0)  # gramos
    estado_sensor: str = "normal"
    calidad_datos: float = Field(1.00, ge=0.0, le=1.0)


class SensorDataCreate(SensorDataBase):
    incubadora_id: uuid.UUID
    paciente_id: Optional[uuid.UUID] = None
    timestamp: Optional[datetime] = None


class SensorData(SensorDataBase):
    id: uuid.UUID
    incubadora_id: uuid.UUID
    paciente_id: Optional[uuid.UUID]
    timestamp: datetime

    class Config:
        from_attributes = True


# Esquemas de Alertas
class AlertaBase(BaseModel):
    tipo_alerta: str = Field(..., max_length=50)
    severidad: AlertaSeveridad = AlertaSeveridad.media
    mensaje: str = Field(..., min_length=10)
    valor_sensor: Optional[float] = None
    umbral_configurado: Optional[float] = None


class AlertaCreate(AlertaBase):
    incubadora_id: uuid.UUID
    paciente_id: Optional[uuid.UUID] = None


class AlertaUpdate(BaseModel):
    estado: AlertaEstado
    usuario_reconocimiento: Optional[uuid.UUID] = None
    tiempo_reconocimiento: Optional[datetime] = None
    tiempo_resolucion: Optional[datetime] = None


class Alerta(AlertaBase):
    id: uuid.UUID
    incubadora_id: uuid.UUID
    paciente_id: Optional[uuid.UUID]
    estado: AlertaEstado
    usuario_reconocimiento: Optional[uuid.UUID]
    tiempo_reconocimiento: Optional[datetime]
    tiempo_resolucion: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Umbrales
class UmbralPacienteBase(BaseModel):
    parametro: str = Field(..., max_length=50)
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    valor_critico_min: Optional[float] = None
    valor_critico_max: Optional[float] = None
    activo: bool = True


class UmbralPacienteCreate(UmbralPacienteBase):
    paciente_id: uuid.UUID


class UmbralPacienteUpdate(BaseModel):
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    valor_critico_min: Optional[float] = None
    valor_critico_max: Optional[float] = None
    activo: Optional[bool] = None


class UmbralPaciente(UmbralPacienteBase):
    id: uuid.UUID
    paciente_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Eventos del Sistema
class EventoSistemaBase(BaseModel):
    tipo_evento: str = Field(..., max_length=50)
    descripcion: Optional[str] = None
    datos_adicionales: Optional[Dict[str, Any]] = None


class EventoSistemaCreate(EventoSistemaBase):
    incubadora_id: Optional[uuid.UUID] = None
    usuario_id: Optional[uuid.UUID] = None
    ip_address: Optional[str] = None


class EventoSistema(EventoSistemaBase):
    id: uuid.UUID
    incubadora_id: Optional[uuid.UUID]
    usuario_id: Optional[uuid.UUID]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Modelos ML
class ModeloMLBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    version: str = Field(..., max_length=20)
    tipo: str = Field(..., max_length=50)
    parametros: Optional[Dict[str, Any]] = None
    metricas_entrenamiento: Optional[Dict[str, Any]] = None
    ruta_archivo: Optional[str] = None


class ModeloMLCreate(ModeloMLBase):
    fecha_entrenamiento: datetime


class ModeloMLUpdate(BaseModel):
    estado: Optional[str] = Field(None, regex=r'^(activo|inactivo|deprecated))')
    parametros: Optional[Dict[str, Any]] = None
    metricas_entrenamiento: Optional[Dict[str, Any]] = None
    ruta_archivo: Optional[str] = None


class ModeloML(ModeloMLBase):
    id: uuid.UUID
    fecha_entrenamiento: datetime
    estado: str
    created_at: datetime

    class Config:
        from_attributes = True


# Esquemas de Predicciones ML
class PrediccionMLBase(BaseModel):
    tipo_prediccion: str = Field(..., max_length=50)
    probabilidad: Optional[float] = Field(None, ge=0.0, le=1.0)
    confianza: Optional[float] = Field(None, ge=0.0, le=1.0)
    datos_entrada: Optional[Dict[str, Any]] = None
    resultado: Optional[Dict[str, Any]] = None
    accion_recomendada: Optional[str] = None


class PrediccionMLCreate(PrediccionMLBase):
    modelo_id: uuid.UUID
    paciente_id: uuid.UUID
    timestamp: Optional[datetime] = None


class PrediccionML(PrediccionMLBase):
    id: uuid.UUID
    modelo_id: uuid.UUID
    paciente_id: uuid.UUID
    timestamp: datetime

    class Config:
        from_attributes = True


# Esquemas para autenticación
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# Esquemas para respuestas de API
class ApiResponse(BaseModel):
    success: bool = True
    message: str = "Operación exitosa"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int


# Esquemas de estadísticas y reportes
class EstadisticasIncubadora(BaseModel):
    incubadora_id: uuid.UUID
    periodo_inicio: datetime
    periodo_fin: datetime
    promedio_temperatura: Optional[float]
    promedio_humedad: Optional[float]
    total_alertas: int
    alertas_criticas: int
    tiempo_actividad: int  # en horas


class ReporteVitalSigns(BaseModel):
    paciente_id: uuid.UUID
    fecha_inicio: datetime
    fecha_fin: datetime
    datos_sensores: List[SensorData]
    alertas_generadas: List[Alerta]
    predicciones_ml: List[PrediccionML]


# Esquemas para configuración de monitoreo en tiempo real
class ConfiguracionMonitoreo(BaseModel):
    incubadora_id: uuid.UUID
    intervalo_muestreo: int = Field(30, ge=10, le=300)  # segundos
    alertas_activas: bool = True
    ml_predictions_activas: bool = True
    umbrales_personalizados: Dict[str, Dict[str, float]] = {}


# Validadores personalizados
class SensorDataBatch(BaseModel):
    """Para recibir múltiples lecturas de sensores de una vez"""
    incubadora_id: uuid.UUID
    readings: List[SensorDataBase]

    @validator('readings')
    def validate_readings_count(cls, v):
        if len(v) > 100:  # Límite de lecturas por batch
            raise ValueError('Máximo 100 lecturas por lote')
        return v


class AlertaQuery(BaseModel):
    """Para filtros de consulta de alertas"""
    incubadora_id: Optional[uuid.UUID] = None
    paciente_id: Optional[uuid.UUID] = None
    severidad: Optional[List[AlertaSeveridad]] = None
    estado: Optional[List[AlertaEstado]] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)