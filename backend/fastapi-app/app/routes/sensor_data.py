"""
Rutas para manejo de datos de sensores
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
import logging

from ..database import get_db
from .. import models, schemas
from ..ml.anomaly_detector import detect_anomalies

logger = logging.getLogger(__name__)
router = APIRouter()


# Crear datos de sensor
@router.post("/", response_model=schemas.SensorData)
async def create_sensor_data(
        sensor_data: schemas.SensorDataCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    Crear nueva lectura de sensor.
    Autom�ticamente ejecuta detecci�n de anomal�as y generaci�n de alertas.
    """
    try:
        # Verificar que la incubadora existe
        incubadora = db.query(models.Incubadora).filter(
            models.Incubadora.id == sensor_data.incubadora_id
        ).first()

        if not incubadora:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incubadora no encontrada"
            )

        # Crear entrada de sensor data
        db_sensor_data = models.SensorData(**sensor_data.dict())
        db.add(db_sensor_data)
        db.commit()
        db.refresh(db_sensor_data)

        # Procesar en background: detecci�n de anomal�as y alertas
        background_tasks.add_task(
            process_sensor_data_background,
            db_sensor_data.id,
            sensor_data.dict()
        )

        logger.info(f"Datos de sensor creados para incubadora {sensor_data.incubadora_id}")
        return db_sensor_data

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando datos de sensor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando datos de sensor: {str(e)}"
        )


# Crear m�ltiples datos de sensor (batch)
@router.post("/batch", response_model=List[schemas.SensorData])
async def create_sensor_data_batch(
        sensor_batch: schemas.SensorDataBatch,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    Crear m�ltiples lecturas de sensor de una vez.
    �til para dispositivos IoT que env�an datos en lotes.
    """
    try:
        # Verificar que la incubadora existe
        incubadora = db.query(models.Incubadora).filter(
            models.Incubadora.id == sensor_batch.incubadora_id
        ).first()

        if not incubadora:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incubadora no encontrada"
            )

        created_records = []

        for reading in sensor_batch.readings:
            # Crear SensorDataCreate con la incubadora_id
            sensor_data_create = schemas.SensorDataCreate(
                incubadora_id=sensor_batch.incubadora_id,
                **reading.dict()
            )

            db_sensor_data = models.SensorData(**sensor_data_create.dict())
            db.add(db_sensor_data)
            created_records.append(db_sensor_data)

        db.commit()

        # Procesar cada registro en background
        for record in created_records:
            db.refresh(record)
            background_tasks.add_task(
                process_sensor_data_background,
                record.id,
                record.__dict__
            )

        logger.info(f"Creados {len(created_records)} registros de sensor para incubadora {sensor_batch.incubadora_id}")
        return created_records

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando lote de datos de sensor: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando lote de datos de sensor: {str(e)}"
        )


# Obtener datos de sensor por ID
@router.get("/{sensor_data_id}", response_model=schemas.SensorData)
def get_sensor_data(sensor_data_id: uuid.UUID, db: Session = Depends(get_db)):
    """Obtener datos de sensor espec�ficos por ID"""

    db_sensor_data = db.query(models.SensorData).filter(
        models.SensorData.id == sensor_data_id
    ).first()

    if not db_sensor_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Datos de sensor no encontrados"
        )

    return db_sensor_data


# Listar datos de sensor con filtros
@router.get("/", response_model=List[schemas.SensorData])
def list_sensor_data(
        incubadora_id: Optional[uuid.UUID] = Query(None),
        paciente_id: Optional[uuid.UUID] = Query(None),
        fecha_inicio: Optional[datetime] = Query(None),
        fecha_fin: Optional[datetime] = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db)
):
    """
    Listar datos de sensor con filtros opcionales.

    - **incubadora_id**: Filtrar por incubadora espec�fica
    - **paciente_id**: Filtrar por paciente espec�fico
    - **fecha_inicio/fecha_fin**: Rango de fechas
    - **limit**: M�ximo n�mero de registros
    - **offset**: Desplazamiento para paginaci�n
    """

    query = db.query(models.SensorData)

    # Aplicar filtros
    if incubadora_id:
        query = query.filter(models.SensorData.incubadora_id == incubadora_id)

    if paciente_id:
        query = query.filter(models.SensorData.paciente_id == paciente_id)

    if fecha_inicio:
        query = query.filter(models.SensorData.timestamp >= fecha_inicio)

    if fecha_fin:
        query = query.filter(models.SensorData.timestamp <= fecha_fin)

    # Ordenar por timestamp descendente y aplicar l�mites
    query = query.order_by(desc(models.SensorData.timestamp))
    query = query.offset(offset).limit(limit)

    return query.all()


# Obtener datos en tiempo real (�ltimos N registros)
@router.get("/realtime/{incubadora_id}", response_model=List[schemas.SensorData])
def get_realtime_data(
        incubadora_id: uuid.UUID,
        minutes: int = Query(5, ge=1, le=60, description="Minutos hacia atr�s"),
        db: Session = Depends(get_db)
):
    """
    Obtener datos de sensor en tiempo real para una incubadora.
    Devuelve los datos de los �ltimos N minutos.
    """

    # Verificar que la incubadora existe
    incubadora = db.query(models.Incubadora).filter(
        models.Incubadora.id == incubadora_id
    ).first()

    if not incubadora:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incubadora no encontrada"
        )

    # Calcular timestamp de corte
    cutoff_time = datetime.now() - timedelta(minutes=minutes)

    # Consultar datos recientes
    sensor_data = db.query(models.SensorData).filter(
        and_(
            models.SensorData.incubadora_id == incubadora_id,
            models.SensorData.timestamp >= cutoff_time
        )
    ).order_by(desc(models.SensorData.timestamp)).all()

    return sensor_data


# Obtener estad�sticas agregadas
@router.get("/stats/{incubadora_id}", response_model=schemas.EstadisticasIncubadora)
def get_sensor_statistics(
        incubadora_id: uuid.UUID,
        fecha_inicio: datetime = Query(...),
        fecha_fin: datetime = Query(...),
        db: Session = Depends(get_db)
):
    """
    Obtener estad�sticas agregadas de una incubadora en un per�odo.
    """

    # Verificar que la incubadora existe
    incubadora = db.query(models.Incubadora).filter(
        models.Incubadora.id == incubadora_id
    ).first()

    if not incubadora:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incubadora no encontrada"
        )

    # Consulta agregada de estad�sticas
    stats = db.query(
        func.avg(models.SensorData.temperatura_incubadora).label('promedio_temperatura'),
        func.avg(models.SensorData.humedad_incubadora).label('promedio_humedad'),
        func.count(models.SensorData.id).label('total_lecturas')
    ).filter(
        and_(
            models.SensorData.incubadora_id == incubadora_id,
            models.SensorData.timestamp >= fecha_inicio,
            models.SensorData.timestamp <= fecha_fin
        )
    ).first()

    # Contar alertas en el per�odo
    total_alertas = db.query(func.count(models.Alerta.id)).filter(
        and_(
            models.Alerta.incubadora_id == incubadora_id,
            models.Alerta.created_at >= fecha_inicio,
            models.Alerta.created_at <= fecha_fin
        )
    ).scalar()

    alertas_criticas = db.query(func.count(models.Alerta.id)).filter(
        and_(
            models.Alerta.incubadora_id == incubadora_id,
            models.Alerta.severidad == 'critica',
            models.Alerta.created_at >= fecha_inicio,
            models.Alerta.created_at <= fecha_fin
        )
    ).scalar()

    # Calcular tiempo de actividad (diferencia en horas)
    tiempo_actividad = int((fecha_fin - fecha_inicio).total_seconds() / 3600)

    return schemas.EstadisticasIncubadora(
        incubadora_id=incubadora_id,
        periodo_inicio=fecha_inicio,
        periodo_fin=fecha_fin,
        promedio_temperatura=float(stats.promedio_temperatura) if stats.promedio_temperatura else None,
        promedio_humedad=float(stats.promedio_humedad) if stats.promedio_humedad else None,
        total_alertas=total_alertas or 0,
        alertas_criticas=alertas_criticas or 0,
        tiempo_actividad=tiempo_actividad
    )


# Eliminar datos antiguos (cleanup)
@router.delete("/cleanup")
async def cleanup_old_data(
        days_old: int = Query(30, ge=1, le=365, description="D�as de antig�edad"),
        db: Session = Depends(get_db)
):
    """
    Eliminar datos de sensor m�s antiguos que N d�as.
    �USAR CON PRECAUCI�N! Esta operaci�n es irreversible.
    """

    cutoff_date = datetime.now() - timedelta(days=days_old)

    # Contar registros a eliminar
    count = db.query(models.SensorData).filter(
        models.SensorData.timestamp < cutoff_date
    ).count()

    if count == 0:
        return {"message": "No hay datos antiguos para eliminar", "deleted": 0}

    # Eliminar datos
    deleted = db.query(models.SensorData).filter(
        models.SensorData.timestamp < cutoff_date
    ).delete()

    db.commit()

    logger.info(f"Eliminados {deleted} registros de sensor m�s antiguos que {days_old} d�as")

    return {
        "message": f"Datos eliminados exitosamente",
        "deleted": deleted,
        "cutoff_date": cutoff_date.isoformat()
    }


# Funci�n para procesar datos de sensor en background
async def process_sensor_data_background(sensor_data_id: uuid.UUID, sensor_data_dict: dict):
    """
    Procesa los datos de sensor en segundo plano:
    1. Detecci�n de anomal�as
    2. Verificaci�n de umbrales
    3. Generaci�n de alertas
    """
    try:
        from ..database import SessionLocal
        db = SessionLocal()

        # Obtener los datos completos del sensor
        sensor_data = db.query(models.SensorData).filter(
            models.SensorData.id == sensor_data_id
        ).first()

        if not sensor_data:
            logger.error(f"No se encontraron datos de sensor con ID {sensor_data_id}")
            return

        # 1. Detecci�n de anomal�as con ML
        try:
            anomaly_result = await detect_anomalies(sensor_data_dict)

            if anomaly_result.get('is_anomaly', False):
                # Crear alerta de anomal�a
                alerta = models.Alerta(
                    incubadora_id=sensor_data.incubadora_id,
                    paciente_id=sensor_data.paciente_id,
                    tipo_alerta='anomalia_detectada',
                    severidad='media',
                    mensaje=f"Anomal�a detectada por ML: {anomaly_result.get('description', 'Sin descripci�n')}",
                    valor_sensor=anomaly_result.get('anomaly_score', 0.0)
                )
                db.add(alerta)
                logger.info(f"Alerta de anomal�a creada para sensor {sensor_data_id}")
        except Exception as e:
            logger.error(f"Error en detecci�n de anomal�as: {e}")

        # 2. Verificaci�n de umbrales cr�ticos
        if sensor_data.paciente_id:
            try:
                await check_critical_thresholds(db, sensor_data)
            except Exception as e:
                logger.error(f"Error verificando umbrales: {e}")

        db.commit()

    except Exception as e:
        logger.error(f"Error procesando datos de sensor en background: {e}")
    finally:
        db.close()


async def check_critical_thresholds(db: Session, sensor_data: models.SensorData):
    """
    Verifica si los valores del sensor exceden umbrales cr�ticos
    """

    # Obtener umbrales del paciente
    umbrales = db.query(models.UmbralPaciente).filter(
        and_(
            models.UmbralPaciente.paciente_id == sensor_data.paciente_id,
            models.UmbralPaciente.activo == True
        )
    ).all()

    # Mapeo de par�metros a valores del sensor
    parametros_sensor = {
        'temperatura_corporal': sensor_data.temperatura_corporal,
        'frecuencia_cardiaca': sensor_data.frecuencia_cardiaca,
        'frecuencia_respiratoria': sensor_data.frecuencia_respiratoria,
        'saturacion_oxigeno': sensor_data.saturacion_oxigeno,
        'temperatura_incubadora': sensor_data.temperatura_incubadora,
        'humedad_incubadora': sensor_data.humedad_incubadora
    }

    for umbral in umbrales:
        valor_actual = parametros_sensor.get(umbral.parametro)

        if valor_actual is None:
            continue

        # Verificar umbrales cr�ticos
        if (umbral.valor_critico_min and valor_actual < umbral.valor_critico_min) or \
                (umbral.valor_critico_max and valor_actual > umbral.valor_critico_max):

            # Crear alerta cr�tica
            alerta = models.Alerta(
                incubadora_id=sensor_data.incubadora_id,
                paciente_id=sensor_data.paciente_id,
                tipo_alerta=f'{umbral.parametro}_critico',
                severidad='critica',
                mensaje=f'{umbral.parametro} en nivel cr�tico: {valor_actual}',
                valor_sensor=float(valor_actual),
                umbral_configurado=float(umbral.valor_critico_min or umbral.valor_critico_max)
            )
            db.add(alerta)
            logger.warning(f"Alerta cr�tica: {umbral.parametro} = {valor_actual}")

        # Verificar umbrales normales
        elif (umbral.valor_min and valor_actual < umbral.valor_min) or \
                (umbral.valor_max and valor_actual > umbral.valor_max):

            # Crear alerta normal
            alerta = models.Alerta(
                incubadora_id=sensor_data.incubadora_id,
                paciente_id=sensor_data.paciente_id,
                tipo_alerta=f'{umbral.parametro}_fuera_rango',
                severidad='media',
                mensaje=f'{umbral.parametro} fuera de rango: {valor_actual}',
                valor_sensor=float(valor_actual),
                umbral_configurado=float(umbral.valor_min or umbral.valor_max)
            )
            db.add(alerta)
            logger.info(f"Alerta: {umbral.parametro} fuera de rango = {valor_actual}")


# WebSocket endpoint para datos en tiempo real
@router.websocket("/ws/{incubadora_id}")
async def websocket_sensor_data(websocket, incubadora_id: uuid.UUID):
    """
    WebSocket para streaming de datos de sensor en tiempo real
    """
    await websocket.accept()

    try:
        while True:
            # Aqu� implementar�as la l�gica de streaming en tiempo real
            # Por ejemplo, consultar la base de datos cada segundo
            # y enviar los datos m�s recientes al cliente

            from ..database import SessionLocal
            db = SessionLocal()

            # Obtener �ltimo dato
            latest_data = db.query(models.SensorData).filter(
                models.SensorData.incubadora_id == incubadora_id
            ).order_by(desc(models.SensorData.timestamp)).first()

            if latest_data:
                data_dict = {
                    "timestamp": latest_data.timestamp.isoformat(),
                    "temperatura_corporal": float(
                        latest_data.temperatura_corporal) if latest_data.temperatura_corporal else None,
                    "frecuencia_cardiaca": latest_data.frecuencia_cardiaca,
                    "saturacion_oxigeno": float(
                        latest_data.saturacion_oxigeno) if latest_data.saturacion_oxigeno else None,
                    "temperatura_incubadora": float(
                        latest_data.temperatura_incubadora) if latest_data.temperatura_incubadora else None,
                    "humedad_incubadora": float(
                        latest_data.humedad_incubadora) if latest_data.humedad_incubadora else None
                }

                await websocket.send_json(data_dict)

            db.close()

            # Esperar 1 segundo antes de la siguiente actualizaci�n
            import asyncio
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
    finally:
        await websocket.close()