-- Inicialización de la base de datos para el sistema de incubadora neonatal
-- PostgreSQL

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Tabla de usuarios (médicos, enfermeras, administradores)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) CHECK (role IN ('admin', 'doctor', 'nurse', 'technician')) DEFAULT 'nurse',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de incubadoras
CREATE TABLE incubadoras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo VARCHAR(20) UNIQUE NOT NULL, -- Código identificador de la incubadora
    modelo VARCHAR(50),
    ubicacion VARCHAR(100), -- Sala, piso, etc.
    estado VARCHAR(20) CHECK (estado IN ('activa', 'inactiva', 'mantenimiento')) DEFAULT 'activa',
    fecha_instalacion DATE,
    ultimo_mantenimiento TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de pacientes (neonatos)
CREATE TABLE pacientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    fecha_nacimiento TIMESTAMP NOT NULL,
    peso_nacimiento DECIMAL(5,2), -- en gramos
    semanas_gestacion INTEGER,
    sexo CHAR(1) CHECK (sexo IN ('M', 'F')),
    identificacion_madre VARCHAR(50),
    medico_asignado UUID REFERENCES users(id),
    incubadora_id UUID REFERENCES incubadoras(id),
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_egreso TIMESTAMP,
    estado VARCHAR(20) CHECK (estado IN ('activo', 'egresado', 'transferido')) DEFAULT 'activo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla principal de datos de sensores
CREATE TABLE sensor_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incubadora_id UUID REFERENCES incubadoras(id) NOT NULL,
    paciente_id UUID REFERENCES pacientes(id),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Variables fisiológicas críticas
    temperatura_corporal DECIMAL(4,2), -- °C
    frecuencia_cardiaca INTEGER, -- BPM
    frecuencia_respiratoria INTEGER, -- RPM
    saturacion_oxigeno DECIMAL(5,2), -- %
    presion_arterial_sistolica INTEGER, -- mmHg
    presion_arterial_diastolica INTEGER, -- mmHg

    -- Variables ambientales de la incubadora
    temperatura_incubadora DECIMAL(4,2), -- °C
    humedad_incubadora DECIMAL(5,2), -- %
    concentracion_oxigeno DECIMAL(5,2), -- %
    presion_aire DECIMAL(8,2), -- Pa
    nivel_ruido DECIMAL(5,2), -- dB

    -- Variables adicionales
    peso_actual DECIMAL(6,2), -- gramos
    estado_sensor VARCHAR(20) DEFAULT 'normal',
    calidad_datos DECIMAL(3,2) DEFAULT 1.00, -- Factor de calidad 0-1

    -- Índices para optimizar consultas temporales
    INDEX idx_sensor_data_timestamp (timestamp),
    INDEX idx_sensor_data_incubadora (incubadora_id, timestamp),
    INDEX idx_sensor_data_paciente (paciente_id, timestamp)
);

-- Tabla de alertas y alarmas
CREATE TABLE alertas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incubadora_id UUID REFERENCES incubadoras(id) NOT NULL,
    paciente_id UUID REFERENCES pacientes(id),
    tipo_alerta VARCHAR(50) NOT NULL, -- 'temperatura_alta', 'bradicardia', 'hipoxia', etc.
    severidad VARCHAR(20) CHECK (severidad IN ('baja', 'media', 'alta', 'critica')) DEFAULT 'media',
    mensaje TEXT NOT NULL,
    valor_sensor DECIMAL(10,4), -- Valor que disparó la alerta
    umbral_configurado DECIMAL(10,4), -- Umbral que se superó
    estado VARCHAR(20) CHECK (estado IN ('activa', 'reconocida', 'resuelta')) DEFAULT 'activa',
    usuario_reconocimiento UUID REFERENCES users(id), -- Quien reconoció la alerta
    tiempo_reconocimiento TIMESTAMP,
    tiempo_resolucion TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de configuración de umbrales por paciente
CREATE TABLE umbrales_paciente (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paciente_id UUID REFERENCES pacientes(id) NOT NULL,
    parametro VARCHAR(50) NOT NULL, -- 'temperatura_corporal', 'frecuencia_cardiaca', etc.
    valor_min DECIMAL(10,4),
    valor_max DECIMAL(10,4),
    valor_critico_min DECIMAL(10,4),
    valor_critico_max DECIMAL(10,4),
    activo BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paciente_id, parametro)
);

-- Tabla de eventos del sistema
CREATE TABLE eventos_sistema (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incubadora_id UUID REFERENCES incubadoras(id),
    usuario_id UUID REFERENCES users(id),
    tipo_evento VARCHAR(50) NOT NULL, -- 'login', 'config_change', 'maintenance', etc.
    descripcion TEXT,
    datos_adicionales JSONB, -- Para almacenar datos estructurados adicionales
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla para almacenar modelos de ML y sus métricas
CREATE TABLE modelos_ml (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(100) NOT NULL,
    version VARCHAR(20) NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- 'anomaly_detection', 'prediction', etc.
    parametros JSONB, -- Hiperparámetros del modelo
    metricas_entrenamiento JSONB, -- Accuracy, precision, recall, etc.
    fecha_entrenamiento TIMESTAMP NOT NULL,
    estado VARCHAR(20) CHECK (estado IN ('activo', 'inactivo', 'deprecated')) DEFAULT 'activo',
    ruta_archivo VARCHAR(255), -- Ruta donde se almacena el modelo serializado
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de predicciones realizadas por ML
CREATE TABLE predicciones_ml (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    modelo_id UUID REFERENCES modelos_ml(id) NOT NULL,
    paciente_id UUID REFERENCES pacientes(id) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tipo_prediccion VARCHAR(50) NOT NULL, -- 'anomalia', 'deterioro_clinico', etc.
    probabilidad DECIMAL(5,4), -- Probabilidad de la predicción (0-1)
    confianza DECIMAL(5,4), -- Nivel de confianza del modelo (0-1)
    datos_entrada JSONB, -- Datos que se usaron para la predicción
    resultado JSONB, -- Resultado detallado de la predicción
    accion_recomendada TEXT
);

-- Crear índices para optimización
CREATE INDEX idx_alertas_estado ON alertas(estado, created_at);
CREATE INDEX idx_alertas_severidad ON alertas(severidad, created_at);
CREATE INDEX idx_eventos_tipo ON eventos_sistema(tipo_evento, created_at);
CREATE INDEX idx_predicciones_timestamp ON predicciones_ml(timestamp);
CREATE INDEX idx_predicciones_paciente ON predicciones_ml(paciente_id, timestamp);

-- Función para actualizar timestamp de updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar trigger de updated_at a las tablas necesarias
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_incubadoras_updated_at BEFORE UPDATE ON incubadoras
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pacientes_updated_at BEFORE UPDATE ON pacientes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_umbrales_updated_at BEFORE UPDATE ON umbrales_paciente
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insertar datos iniciales
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
('admin', 'admin@hospital.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj1/3CwjhYCu', 'Administrador Sistema', 'admin'),
('dr_smith', 'smith@hospital.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj1/3CwjhYCu', 'Dr. John Smith', 'doctor'),
('enfermera_maria', 'maria@hospital.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj1/3CwjhYCu', 'María González', 'nurse');

INSERT INTO incubadoras (codigo, modelo, ubicacion, estado) VALUES
('INC-001', 'MediTech Neo 3000', 'UCI Neonatal - Sala A', 'activa'),
('INC-002', 'MediTech Neo 3000', 'UCI Neonatal - Sala A', 'activa'),
('INC-003', 'CareTech Advanced', 'UCI Neonatal - Sala B', 'activa');

-- Comentarios de documentación
COMMENT ON TABLE sensor_data IS 'Almacena todos los datos de sensores de las incubadoras en tiempo real';
COMMENT ON TABLE alertas IS 'Registro de todas las alertas y alarmas del sistema';
COMMENT ON TABLE modelos_ml IS 'Metadatos y versiones de los modelos de machine learning';
COMMENT ON TABLE predicciones_ml IS 'Resultados de predicciones realizadas por los modelos de IA';