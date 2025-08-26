"""
Aplicación principal FastAPI para el sistema de incubadora neonatal
"""

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
import logging
import os
from datetime import datetime

# Imports locales
from .database import init_database, get_db
from .routes import sensor_data, alerts, auth
from . import schemas

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Lifespan context manager para inicialización y cleanup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Iniciando aplicación FastAPI...")
    try:
        await init_database()
        logger.info("Sistema de incubadora neonatal inicializado correctamente")
    except Exception as e:
        logger.error(f"Error durante la inicialización: {e}")
        raise

    yield

    # Shutdown
    logger.info("Cerrando aplicación FastAPI...")


# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Incubadora Neonatal",
    description="""
    Sistema de monitoreo remoto y predictivo para incubadoras neonatales.

    Características principales:
    - Monitoreo en tiempo real de signos vitales
    - Alertas inteligentes y predictivas
    - Análisis de datos con Machine Learning
    - Dashboard web y móvil
    - Integración IoT con microcontroladores
    """,
    version="1.0.0",
    contact={
        "name": "Equipo de Desarrollo",
        "email": "desarrollo@hospital.com",
    },
    license_info={
        "name": "MIT License",
    },
    lifespan=lifespan
)

# Configuración de CORS
origins = [
    "http://localhost:3000",  # React development
    "http://localhost:8080",  # Vue development
    "http://localhost:4200",  # Angular development
    "https://incubadora-app.hospital.com",  # Producción
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# Middleware de hosts confiables (para producción)
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["incubadora-api.hospital.com", "localhost"]
    )

# Seguridad
security = HTTPBearer()

# Incluir routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
app.include_router(sensor_data.router, prefix="/api/v1/sensors", tags=["Datos de Sensores"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alertas"])


# Endpoint de health check
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Endpoint para verificar el estado del sistema"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "Incubadora Neonatal API"
    }


# Endpoint raíz
@app.get("/", tags=["Sistema"])
async def root():
    """Endpoint raíz con información del sistema"""
    return {
        "message": "Sistema de Incubadora Neonatal API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# Endpoint para información del sistema
@app.get("/api/v1/system/info", tags=["Sistema"])
async def system_info():
    """Información detallada del sistema"""
    return {
        "name": "Sistema de Incubadora Neonatal",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "python_version": "3.9+",
        "framework": "FastAPI",
        "database": "PostgreSQL",
        "features": [
            "Monitoreo en tiempo real",
            "Alertas inteligentes",
            "Machine Learning predictivo",
            "Dashboard web",
            "Integración IoT"
        ]
    }


# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request, call_next):
    start_time = datetime.now()

    response = await call_next(request)

    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"{request.method} {request.url} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )

    return response


# Handler de errores globales
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Error interno del servidor"
    )


# Configuración para desarrollo
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )