"""
Rutas para manejo de alertas y alarmas del sistema
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, or_
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
import logging

from ..database import get_db
from .. import models, schemas

logger = logging.getLogger(__name__)
router = APIRouter()


# Crear alerta manualmente
@router.post("/", response_model=schemas.Alerta)
async def create_alert(
        alert: schemas.AlertaCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """
    Crear nueva alerta manualmente.
    Útil para alertas generadas por el personal médico.
    """
    try:
        # Verificar que la incubadora existe
        incubadora = db.query(models.Incubadora).filter(
            models.Incubadora.id == alert.incubadora_id
        ).first()

        if not incubadora:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incubadora no encontrada"
            )

        # Verificar paciente si se especifica
        if alert.paciente_id:
            paciente = db.query(models.Paciente).filter(
                models.Paciente.id == alert.paciente_id
            ).first()

            if not paciente:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Paciente no encontrado"
                )

        # Crear alerta
        db_alert = models.Alerta(**alert.dict())
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)

        # Procesar notificaciones en background
        background_tasks.add_task(
            process_alert_notifications,
            db_alert.id
        )

        logger.info(f"Alerta creada: {alert.tipo_alerta} - Severidad: {alert.severidad}")
        return db_alert

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando alerta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando alerta: {str(e)}"
        )


# Obtener alerta por ID
@router.get("/{alert_id}", response_model=schemas.Alerta)
def get_alert(alert_id: uuid.UUID, db: Session = Depends(get_db)):
    """Obtener alerta específica por ID"""

    db_alert = db.query(models.Alerta).filter(
        models.Alerta.id == alert_id
    ).first()

    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada"
        )

    return db_alert


# Listar alertas con filtros avanzados
@router.get("/", response_model=List[schemas.Alerta])
def list_alerts(
        incubadora_id: Optional[uuid.UUID] = Query(None),
        paciente_id: Optional[uuid.UUID] = Query(None),
        severidad: Optional[List[str]] = Query(None),
        estado: Optional[List[str]] = Query(None),
        tipo_alerta: Optional[str] = Query(None),
        fecha_inicio: Optional[datetime] = Query(None),
        fecha_fin: Optional[datetime] = Query(None),
        only_active: bool = Query(False, description="Solo alertas activas"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db)
):
    """
    Listar alertas con filtros avanzados.

    - **incubadora_id**: Filtrar por incubadora específica
    - **paciente_id**: Filtrar por paciente específico
    - **severidad**: Lista de severidades (baja, media, alta, critica)
    - **estado**: Lista de estados (activa, reconocida, resuelta)
    - **tipo_alerta**: Tipo específico de alerta
    - **fecha_inicio/fecha_fin**: Rango de fechas
    - **only_active**: Solo alertas activas (no reconocidas ni resueltas)
    """

    query = db.query(models.Alerta)

    # Aplicar filtros
    if incubadora_id:
        query = query.filter(models.Alerta.incubadora_id == incubadora_id)

    if paciente_id:
        query = query.filter(models.Alerta.paciente_id == paciente_id)

    if severidad:
        query = query.filter(models.Alerta.severidad.in_(severidad))

    if estado:
        query = query.filter(models.Alerta.estado.in_(estado))

    if tipo_alerta:
        query = query.filter(models.Alerta.tipo_alerta.like(f"%{tipo_alerta}%"))

    if fecha_inicio:
        query = query.filter(models.Alerta.created_at >= fecha_inicio)

    if fecha_fin:
        query = query.filter(models.Alerta.created_at <= fecha_fin)

    if only_active:
        query = query.filter(models.Alerta.estado == 'activa')

    # Ordenar por fecha de creación descendente y aplicar límites
    query = query.order_by(desc(models.Alerta.created_at))
    query = query.offset(offset).limit(limit)

    return query.all()


# Obtener alertas críticas en tiempo real
@router.get("/critical/active", response_model=List[schemas.Alerta])
def get_critical_active_alerts(
        incubadora_id: Optional[uuid.UUID] = Query(None),
        db: Session = Depends(get_db)
):
    """
    Obtener todas las alertas críticas activas.
    Útil para dashboard de monitoreo en tiempo real.
    """

    query = db.query(models.Alerta).filter(
        and_(
            models.Alerta.severidad == 'critica',
            models.Alerta.estado == 'activa'
        )
    )

    if incubadora_id:
        query = query.filter(models.Alerta.incubadora_id == incubadora_id)

    query = query.order_by(desc(models.Alerta.created_at))

    return query.all()


# Reconocer alerta
@router.patch("/{alert_id}/acknowledge", response_model=schemas.Alerta)
def acknowledge_alert(
        alert_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session = Depends(get_db)
):
    """
    Reconocer una alerta (marcarla como vista por el personal).
    """

    # Buscar alerta
    db_alert = db.query(models.Alerta).filter(
        models.Alerta.id == alert_id
    ).first()

    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada"
        )

    # Verificar que el usuario existe
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Actualizar alerta
    db_alert.estado = 'reconocida'
    db_alert.usuario_reconocimiento = user_id
    db_alert.tiempo_reconocimiento = datetime.now()

    db.commit()
    db.refresh(db_alert)

    logger.info(f"Alerta {alert_id} reconocida por usuario {user_id}")
    return db_alert


# Resolver alerta
@router.patch("/{alert_id}/resolve", response_model=schemas.Alerta)
def resolve_alert(
        alert_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session = Depends(get_db)
):
    """
    Resolver una alerta (marcarla como solucionada).
    """

    # Buscar alerta
    db_alert = db.query(models.Alerta).filter(
        models.Alerta.id == alert_id
    ).first()

    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada"
        )

    # Verificar que el usuario existe
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Actualizar alerta
    db_alert.estado = 'resuelta'
    if not db_alert.usuario_reconocimiento:
        db_alert.usuario_reconocimiento = user_id
        db_alert.tiempo_reconocimiento = datetime.now()

    db_alert.tiempo_resolucion = datetime.now()

    db.commit()
    db.refresh(db_alert)

    logger.info(f"Alerta {alert_id} resuelta por usuario {user_id}")
    return db_alert


# Estadísticas de alertas
@router.get("/stats/summary", response_model=dict)
def get_alerts_summary(
        incubadora_id: Optional[uuid.UUID] = Query(None),
        fecha_inicio: Optional[datetime] = Query(None),
        fecha_fin: Optional[datetime] = Query(None),
        db: Session = Depends(get_db)
):
    """
    Obtener resumen estadístico de alertas.
    """

    # Si no se especifican fechas, usar últimos 7 días
    if not fecha_inicio:
        fecha_inicio = datetime.now() - timedelta(days=7)
    if not fecha_fin:
        fecha_fin = datetime.now()

    base_query = db.query(models.Alerta).filter(
        and_(
            models.Alerta.created_at >= fecha_inicio,
            models.Alerta.created_at <= fecha_fin
        )
    )

    if incubadora_id:
        base_query = base_query.filter(models.Alerta.incubadora_id == incubadora_id)

    # Contar por severidad
    severidad_stats = {}
    for severidad in ['baja', 'media', 'alta', 'critica']:
        count = base_query.filter(models.Alerta.severidad == severidad).count()
        severidad_stats[severidad] = count

    # Contar por estado
    estado_stats = {}
    for estado in ['activa', 'reconocida', 'resuelta']:
        count = base_query.filter(models.Alerta.estado == estado).count()
        estado_stats[estado] = count

    # Alertas por tipo más comunes
    tipo_stats = db.query(
        models.Alerta.tipo_alerta,
        func.count(models.Alerta.id).label('count')
    ).filter(
        and_(
            models.Alerta.created_at >= fecha_inicio,
            models.Alerta.created_at <= fecha_fin
        )
    )

    if incubadora_id:
        tipo_stats = tipo_stats.filter(models.Alerta.incubadora_id == incubadora_id)

    tipo_stats = tipo_stats.group_by(models.Alerta.tipo_alerta) \
        .order_by(desc('count')) \
        .limit(10).all()

    # Tiempo promedio de respuesta
    response_time_query = base_query.filter(
        models.Alerta.tiempo_reconocimiento.isnot(None)
    )

    avg_response_time = None
    if response_time_query.count() > 0:
        # Calcular promedio de tiempo de respuesta en minutos
        response_times = []
        for alert in response_time_query:
            if alert.tiempo_reconocimiento:
                diff = (alert.tiempo_reconocimiento - alert.created_at).total_seconds() / 60
                response_times.append(diff)

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)

    return {
        "periodo": {
            "inicio": fecha_inicio.isoformat(),
            "fin": fecha_fin.isoformat()
        },
        "total_alertas": base_query.count(),
        "por_severidad": severidad_stats,
        "por_estado": estado_stats,
        "tipos_mas_comunes": [
            {"tipo": row.tipo_alerta, "count": row.count}
            for row in tipo_stats
        ],
        "tiempo_promedio_respuesta_minutos": avg_response_time,
        "incubadora_id": str(incubadora_id) if incubadora_id else None
    }


# Obtener trending de alertas (últimas 24 horas por horas)
@router.get("/stats/trending", response_model=List[dict])
def get_alerts_trending(
        incubadora_id: Optional[uuid.UUID] = Query(None),
        hours: int = Query(24, ge=1, le=168, description="Horas hacia atrás"),
        db: Session = Depends(get_db)
):
    """
    Obtener tendencia de alertas por horas.
    Útil para gráficos de tendencia en dashboard.
    """

    # Calcular rango de tiempo
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    # Query con agrupación por hora
    query = db.query(
        func.date_trunc('hour', models.Alerta.created_at).label('hour'),
        func.count(models.Alerta.id).label('total'),
        func.sum(func.case([(models.Alerta.severidad == 'critica', 1)], else_=0)).label('criticas'),
        func.sum(func.case([(models.Alerta.severidad == 'alta', 1)], else_=0)).label('altas')
    ).filter(
        and_(
            models.Alerta.created_at >= start_time,
            models.Alerta.created_at <= end_time
        )
    )

    if incubadora_id:
        query = query.filter(models.Alerta.incubadora_id == incubadora_id)

    results = query.group_by('hour').order_by('hour').all()

    return [
        {
            "hora": row.hour.isoformat(),
            "total": row.total,
            "criticas": row.criticas or 0,
            "altas": row.altas or 0
        }
        for row in results
    ]


# Función para procesar notificaciones de alertas en background
async def process_alert_notifications(alert_id: uuid.UUID):
    """
    Procesa notificaciones para una alerta en segundo plano.
    Puede incluir: emails, SMS, push notifications, etc.
    """
    try:
        from ..database import SessionLocal
        db = SessionLocal()

        # Obtener la alerta
        alert = db.query(models.Alerta).filter(
            models.Alerta.id == alert_id
        ).first()

        if not alert:
            logger.error(f"Alerta {alert_id} no encontrada para notificaciones")
            return

        # Simular envío de notificaciones basado en severidad
        if alert.severidad in ['critica', 'alta']:
            # Notificaciones inmediatas para alertas críticas/altas
            logger.info(f"Enviando notificación URGENTE para alerta {alert_id}: {alert.mensaje}")

            # Aquí implementarías el envío real de notificaciones:
            # - Email a médicos de turno
            # - SMS a personal de emergencia
            # - Push notification a app móvil
            # - Activar alarmas sonoras físicas

        else:
            # Notificaciones regulares para alertas menores
            logger.info(f"Enviando notificación para alerta {alert_id}: {alert.mensaje}")

            # Notificaciones menos urgentes:
            # - Email regular
            # - Notificación en dashboard

        # Registrar evento de notificación
        evento = models.EventoSistema(
            incubadora_id=alert.incubadora_id,
            tipo_evento='notificacion_alerta',
            descripcion=f'Notificación enviada para alerta {alert.tipo_alerta}',
            datos_adicionales={
                'alert_id': str(alert_id),
                'severidad': alert.severidad,
                'tipo': alert.tipo_alerta
            }
        )
        db.add(evento)
        db.commit()

    except Exception as e:
        logger.error(f"Error procesando notificaciones para alerta {alert_id}: {e}")
    finally:
        db.close()


# WebSocket para alertas en tiempo real
@router.websocket("/ws/realtime")
async def websocket_alerts_realtime(websocket):
    """
    WebSocket para recibir alertas en tiempo real.
    El cliente puede suscribirse a alertas de incubadoras específicas.
    """
    await websocket.accept()

    try:
        # Recibir configuración inicial del cliente
        config = await websocket.receive_json()
        incubadora_ids = config.get('incubadora_ids', [])

        while True:
            from ..database import SessionLocal
            db = SessionLocal()

            # Consultar alertas activas recientes (últimos 30 segundos)
            recent_time = datetime.now() - timedelta(seconds=30)

            query = db.query(models.Alerta).filter(
                and_(
                    models.Alerta.estado == 'activa',
                    models.Alerta.created_at >= recent_time
                )
            )

            if incubadora_ids:
                query = query.filter(models.Alerta.incubadora_id.in_(incubadora_ids))

            recent_alerts = query.all()

            for alert in recent_alerts:
                alert_data = {
                    "id": str(alert.id),
                    "incubadora_id": str(alert.incubadora_id),
                    "paciente_id": str(alert.paciente_id) if alert.paciente_id else None,
                    "tipo_alerta": alert.tipo_alerta,
                    "severidad": alert.severidad,
                    "mensaje": alert.mensaje,
                    "valor_sensor": float(alert.valor_sensor) if alert.valor_sensor else None,
                    "created_at": alert.created_at.isoformat(),
                    "timestamp": datetime.now().isoformat()
                }

                await websocket.send_json(alert_data)

            db.close()

            # Esperar 5 segundos antes de la siguiente consulta
            import asyncio
            await asyncio.sleep(5)

    except Exception as e:
        logger.error(f"Error en WebSocket de alertas: {e}")
    finally:
        await websocket.close()