"""
Rutas para autenticación y autorización
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
import os
import uuid
import logging

from ..database import get_db
from .. import models, schemas

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# Configuración JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "tu-clave-secreta-super-segura-aqui")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 horas


# Funciones utilitarias para JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crear token JWT de acceso"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verificar y decodificar token JWT"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return schemas.TokenData(username=username)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token_data: schemas.TokenData = Depends(verify_token), db: Session = Depends(get_db)):
    """Obtener usuario actual desde el token"""
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )
    return user


def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    """Obtener usuario actual activo"""
    return current_user


# Funciones de hashing de contraseñas
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verificar contraseña"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Generar hash de contraseña"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def authenticate_user(db: Session, username: str, password: str):
    """Autenticar usuario"""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user


# Endpoints de autenticación

@router.post("/login", response_model=schemas.Token)
async def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Iniciar sesión con username y password.
    Devuelve token JWT para autenticación en requests posteriores.
    """
    try:
        # Autenticar usuario
        user = authenticate_user(db, login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario inactivo"
            )

        # Crear token de acceso
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role},
            expires_delta=access_token_expires
        )

        # Registrar evento de login
        evento = models.EventoSistema(
            usuario_id=user.id,
            tipo_evento='user_login',
            descripcion=f'Login exitoso para usuario {user.username}'
        )
        db.add(evento)
        db.commit()

        logger.info(f"Login exitoso para usuario: {user.username}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # en segundos
        }

    except Exception as e:
        logger.error(f"Error en login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno durante autenticación"
        )


@router.post("/register", response_model=schemas.User)
async def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registrar nuevo usuario.
    Solo usuarios admin pueden crear nuevos usuarios.
    """
    try:
        # Verificar si username ya existe
        existing_user = db.query(models.User).filter(
            models.User.username == user_data.username
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El username ya está en uso"
            )

        # Verificar si email ya existe
        existing_email = db.query(models.User).filter(
            models.User.email == user_data.email
        ).first()

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está en uso"
            )

        # Crear hash de contraseña
        hashed_password = get_password_hash(user_data.password)

        # Crear usuario
        db_user = models.User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Registrar evento
        evento = models.EventoSistema(
            usuario_id=db_user.id,
            tipo_evento='user_created',
            descripcion=f'Usuario creado: {db_user.username}'
        )
        db.add(evento)
        db.commit()

        logger.info(f"Usuario creado: {db_user.username}")
        return db_user

    except Exception as e:
        db.rollback()
        logger.error(f"Error creando usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando usuario: {str(e)}"
        )


@router.get("/me", response_model=schemas.User)
async def get_current_user_info(current_user: models.User = Depends(get_current_active_user)):
    """
    Obtener información del usuario actual.
    """
    return current_user


@router.put("/me", response_model=schemas.User)
async def update_current_user(
        user_update: schemas.UserUpdate,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """
    Actualizar información del usuario actual.
    """
    try:
        # Actualizar campos proporcionados
        update_data = user_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            if field == 'username' and value != current_user.username:
                # Verificar que el nuevo username no esté en uso
                existing = db.query(models.User).filter(
                    models.User.username == value
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El username ya está en uso"
                    )

            if field == 'email' and value != current_user.email:
                # Verificar que el nuevo email no esté en uso
                existing = db.query(models.User).filter(
                    models.User.email == value
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El email ya está en uso"
                    )

            setattr(current_user, field, value)

        db.commit()
        db.refresh(current_user)

        logger.info(f"Usuario actualizado: {current_user.username}")
        return current_user

    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando usuario: {str(e)}"
        )


@router.post("/change-password")
async def change_password(
        current_password: str,
        new_password: str,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """
    Cambiar contraseña del usuario actual.
    """
    try:
        # Verificar contraseña actual
        if not verify_password(current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contraseña actual incorrecta"
            )

        # Validar nueva contraseña
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 8 caracteres"
            )

        # Actualizar contraseña
        current_user.password_hash = get_password_hash(new_password)
        db.commit()

        # Registrar evento
        evento = models.EventoSistema(
            usuario_id=current_user.id,
            tipo_evento='password_changed',
            descripcion=f'Contraseña cambiada para usuario {current_user.username}'
        )
        db.add(evento)
        db.commit()

        logger.info(f"Contraseña cambiada para usuario: {current_user.username}")

        return {"message": "Contraseña actualizada exitosamente"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error cambiando contraseña: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cambiando contraseña: {str(e)}"
        )


@router.post("/logout")
async def logout(
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """
    Cerrar sesión (invalidar token).
    En una implementación real, mantendrías una blacklist de tokens.
    """
    try:
        # Registrar evento de logout
        evento = models.EventoSistema(
            usuario_id=current_user.id,
            tipo_evento='user_logout',
            descripcion=f'Logout para usuario {current_user.username}'
        )
        db.add(evento)
        db.commit()

        logger.info(f"Logout para usuario: {current_user.username}")

        return {"message": "Sesión cerrada exitosamente"}

    except Exception as e:
        logger.error(f"Error en logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error cerrando sesión"
        )


# Dependencias de autorización por rol
def require_role(required_role: str):
    """
    Decorator para requerir un rol específico.
    """

    def role_checker(current_user: models.User = Depends(get_current_active_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere rol: {required_role}"
            )
        return current_user

    return role_checker


def require_any_role(allowed_roles: list):
    """
    Decorator para requerir uno de varios roles.
    """

    def role_checker(current_user: models.User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Roles permitidos: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


# Endpoints administrativos (solo admins)
@router.get("/users", response_model=list[schemas.User])
async def list_users(
        current_user: models.User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
):
    """
    Listar todos los usuarios (solo administradores).
    """
    users = db.query(models.User).all()
    return users


@router.get("/users/{user_id}", response_model=schemas.User)
async def get_user(
        user_id: uuid.UUID,
        current_user: models.User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
):
    """
    Obtener usuario específico por ID (solo administradores).
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user


@router.put("/users/{user_id}", response_model=schemas.User)
async def update_user(
        user_id: uuid.UUID,
        user_update: schemas.UserUpdate,
        current_user: models.User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
):
    """
    Actualizar usuario específico (solo administradores).
    """
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Actualizar campos proporcionados
        update_data = user_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)

        logger.info(f"Usuario {user_id} actualizado por admin {current_user.username}")
        return user

    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando usuario {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando usuario: {str(e)}"
        )


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: uuid.UUID,
        current_user: models.User = Depends(require_role("admin")),
        db: Session = Depends(get_db)
):
    """
    Desactivar usuario (no eliminar físicamente).
    """
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # No permitir desactivar al propio admin
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes desactivar tu propia cuenta"
            )

        # Desactivar usuario en lugar de eliminarlo
        user.is_active = False
        db.commit()

        logger.info(f"Usuario {user_id} desactivado por admin {current_user.username}")

        return {"message": "Usuario desactivado exitosamente"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error desactivando usuario {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error desactivando usuario: {str(e)}"
        )


# Endpoint para verificar token (útil para frontend)
@router.get("/verify-token")
async def verify_token_endpoint(current_user: models.User = Depends(get_current_active_user)):
    """
    Verificar si el token actual es válido.
    """
    return {
        "valid": True,
        "user": current_user.username,
        "role": current_user.role,
        "expires": "Token válido"
    }