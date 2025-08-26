"""
Configuración de la base de datos PostgreSQL
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables de entorno para la base de datos
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/incubadora_neonatal"
)

# Crear engine de SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
)

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Función para crear las tablas
def create_tables():
    """Crea todas las tablas en la base de datos"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas exitosamente")
    except Exception as e:
        logger.error(f"Error creando tablas: {e}")
        raise


# Dependency para obtener la sesión de base de datos
def get_db():
    """
    Dependency que proporciona una sesión de base de datos.
    Se usa en los endpoints de FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Clase para operaciones de base de datos
class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def get_session(self):
        """Obtiene una nueva sesión de base de datos"""
        return self.SessionLocal()

    def create_all_tables(self):
        """Crea todas las tablas definidas en los modelos"""
        Base.metadata.create_all(bind=self.engine)

    def drop_all_tables(self):
        """CUIDADO: Elimina todas las tablas"""
        Base.metadata.drop_all(bind=self.engine)

    def test_connection(self):
        """Prueba la conexión a la base de datos"""
        try:
            with self.engine.connect() as connection:
                result = connection.execute("SELECT 1")
                logger.info("Conexión a base de datos exitosa")
                return True
        except Exception as e:
            logger.error(f"Error conectando a base de datos: {e}")
            return False


# Instancia global del manager
db_manager = DatabaseManager()


# Función para inicializar la base de datos
async def init_database():
    """Inicializa la base de datos al arrancar la aplicación"""
    try:
        # Verificar conexión
        if not db_manager.test_connection():
            raise Exception("No se puede conectar a la base de datos")

        # Crear tablas si no existen
        db_manager.create_all_tables()

        logger.info("Base de datos inicializada correctamente")

    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        raise


# Funciones utilitarias para transacciones
def execute_with_retry(func, max_retries=3):
    """Ejecuta una función con reintentos en caso de error de BD"""
    import time

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Intento {attempt + 1} falló: {e}. Reintentando...")
            time.sleep(2 ** attempt)  # Backoff exponencial