"""
Modelos SQLAlchemy para el sistema de incubadora neonatal
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, JSON, DECIMAL, \
    CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default='nurse')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relaciones
    pacientes_asignados = relationship("Paciente", back_populates="medico")
    alertas_reconocidas = relationship("Alerta", back_populates="usuario_reconocimiento")
    eventos = relationship("EventoSistema", back_populates="usuario")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'doctor', 'nurse', 'technician')", name='check_user_role'),
    )


class Incubadora(Base):
    __tablename__ = "incubadoras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(20), unique=True, nullable=False)
    modelo = Column(String(50))
    ubicacion = Column(String(100))
    estado = Column(String(20), default='activa')
    fecha_instalacion = Column(DateTime)
    ultimo_mantenimiento = Column(DateTime)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relaciones
    pacientes = relationship("Paciente", back_populates="incubadora")
    sensor_data = relationship("SensorData", back_populates="incubadora")
    alertas = relationship("Alerta", back_populates="incubadora")
    eventos = relationship("EventoSistema", back_populates="incubadora")

    __table_args__ = (
        CheckConstraint("estado IN ('activa', 'inactiva', 'mantenimiento')", name='check_incubadora_estado'),
    )


class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    fecha_nacimiento = Column(DateTime, nullable=False)
    peso_nacimiento = Column(DECIMAL(5, 2))
    semanas_gestacion = Column(Integer)
    sexo = Column(String(1))
    identificacion_madre = Column(String(50))
    medico_asignado = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    incubadora_id = Column(UUID(as_uuid=True), ForeignKey('incubadoras.id'))
    fecha_ingreso = Column(DateTime, default=func.current_timestamp())
    fecha_egreso = Column(DateTime)
    estado = Column(String(20), default='activo')
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relaciones
    medico = relationship("User", back_populates="pacientes_asignados")
    incubadora = relationship("Incubadora", back_populates="pacientes")
    sensor_data = relationship("SensorData", back_populates="paciente")
    alertas = relationship("Alerta", back_populates="paciente")
    umbrales = relationship("UmbralPaciente", back_populates="paciente")
    predicciones = relationship("PrediccionML", back_populates="paciente")

    __table_args__ = (
        CheckConstraint("sexo IN ('M', 'F')", name='check_paciente_sexo'),
        CheckConstraint("estado IN ('activo', 'egresado', 'transferido')", name='check_paciente_estado'),
    )


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incubadora_id = Column(UUID(as_uuid=True), ForeignKey('incubadoras.id'), nullable=False)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey('pacientes.id'))
    timestamp = Column(DateTime, nullable=False, default=func.current_timestamp())

    # Variables fisiológicas críticas
    temperatura_corporal = Column(DECIMAL(4, 2))
    frecuencia_cardiaca = Column(Integer)
    frecuencia_respiratoria = Column(Integer)
    saturacion_oxigeno = Column(DECIMAL(5, 2))
    presion_arterial_sistolica = Column(Integer)
    presion_arterial_diastolica = Column(Integer)

    # Variables ambientales de la incubadora
    temperatura_incubadora = Column(DECIMAL(4, 2))
    humedad_incubadora = Column(DECIMAL(5, 2))
    concentracion_oxigeno = Column(DECIMAL(5, 2))
    presion_aire = Column(DECIMAL(8, 2))
    nivel_ruido = Column(DECIMAL(5, 2))

    # Variables adicionales
    peso_actual = Column(DECIMAL(6, 2))
    estado_sensor = Column(String(20), default='normal')
    calidad_datos = Column(DECIMAL(3, 2), default=1.00)

    # Relaciones
    incubadora = relationship("Incubadora", back_populates="sensor_data")
    paciente = relationship("Paciente", back_populates="sensor_data")


class Alerta(Base):
    __tablename__ = "alertas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incubadora_id = Column(UUID(as_uuid=True), ForeignKey('incubadoras.id'), nullable=False)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey('pacientes.id'))
    tipo_alerta = Column(String(50), nullable=False)
    severidad = Column(String(20), default='media')
    mensaje = Column(Text, nullable=False)
    valor_sensor = Column(DECIMAL(10, 4))
    umbral_configurado = Column(DECIMAL(10, 4))
    estado = Column(String(20), default='activa')
    usuario_reconocimiento = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    tiempo_reconocimiento = Column(DateTime)
    tiempo_resolucion = Column(DateTime)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relaciones
    incubadora = relationship("Incubadora", back_populates="alertas")
    paciente = relationship("Paciente", back_populates="alertas")
    usuario_reconocimiento = relationship("User", back_populates="alertas_reconocidas")

    __table_args__ = (
        CheckConstraint("severidad IN ('baja', 'media', 'alta', 'critica')", name='check_alerta_severidad'),
        CheckConstraint("estado IN ('activa', 'reconocida', 'resuelta')", name='check_alerta_estado'),
    )


class UmbralPaciente(Base):
    __tablename__ = "umbrales_paciente"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey('pacientes.id'), nullable=False)
    parametro = Column(String(50), nullable=False)
    valor_min = Column(DECIMAL(10, 4))
    valor_max = Column(DECIMAL(10, 4))
    valor_critico_min = Column(DECIMAL(10, 4))
    valor_critico_max = Column(DECIMAL(10, 4))
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relaciones
    paciente = relationship("Paciente", back_populates="umbrales")


class EventoSistema(Base):
    __tablename__ = "eventos_sistema"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incubadora_id = Column(UUID(as_uuid=True), ForeignKey('incubadoras.id'))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    tipo_evento = Column(String(50), nullable=False)
    descripcion = Column(Text)
    datos_adicionales = Column(JSONB)
    ip_address = Column(INET)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relaciones
    incubadora = relationship("Incubadora", back_populates="eventos")
    usuario = relationship("User", back_populates="eventos")


class ModeloML(Base):
    __tablename__ = "modelos_ml"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    tipo = Column(String(50), nullable=False)
    parametros = Column(JSONB)
    metricas_entrenamiento = Column(JSONB)
    fecha_entrenamiento = Column(DateTime, nullable=False)
    estado = Column(String(20), default='activo')
    ruta_archivo = Column(String(255))
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relaciones
    predicciones = relationship("PrediccionML", back_populates="modelo")

    __table_args__ = (
        CheckConstraint("estado IN ('activo', 'inactivo', 'deprecated')", name='check_modelo_estado'),
    )


class PrediccionML(Base):
    __tablename__ = "predicciones_ml"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    modelo_id = Column(UUID(as_uuid=True), ForeignKey('modelos_ml.id'), nullable=False)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey('pacientes.id'), nullable=False)
    timestamp = Column(DateTime, default=func.current_timestamp())
    tipo_prediccion = Column(String(50), nullable=False)
    probabilidad = Column(DECIMAL(5, 4))
    confianza = Column(DECIMAL(5, 4))
    datos_entrada = Column(JSONB)
    resultado = Column(JSONB)
    accion_recomendada = Column(Text)

    # Relaciones
    modelo = relationship("ModeloML", back_populates="predicciones")
    paciente = relationship("Paciente", back_populates="predicciones")