"""
Rutas de autenticación para la API del sistema de incubadora neonatal
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import jwt
import logging

from ..shared.python.utils import hash_password, verify_password, generate_secure_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

# Configuración JWT (en producción debería estar en variables de entorno)
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class LoginRequest(BaseModel):
    """Modelo para request de login"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Modelo para response de login"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: dict


class UserCreate(BaseModel):
    """Modelo para crear usuario"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(default="user", regex=r'^(admin|doctor|nurse|user)$')


class User(BaseModel):
    """Modelo de usuario"""
    id: Optional[str] = None
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool = True
    created_at: Optional[datetime] = None


# Base de datos simulada de usuarios (en producción usar base de datos real)
fake_users_db = {
    "admin": {
        "id": "1",
        "username": "admin",
        "email": "admin@incubadora.com",
        "full_name": "Administrador Sistema",
        "role": "admin",
        "hashed_password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # password: 'admin123'
        "salt": "admin_salt",
        "is_active": True,
        "created_at": datetime.utcnow()
    },
    "doctor": {
        "id": "2",
        "username": "doctor",
        "email": "doctor@hospital.com",
        "full_name": "Dr. Juan Pérez",
        "role": "doctor",
        "hashed_password": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",  # password: 'doctor123'
        "salt": "doctor_salt",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Autentica un usuario con username y password
    """
    user = fake_users_db.get(username)
    if not user:
        return None

    if not verify_password(password, user["hashed_password"], user["salt"]):
        return None

    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Crea un token JWT de acceso
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Obtiene el usuario actual desde el token JWT
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Obtiene el usuario actual si está activo
    """
    if not current_user.get("is_active"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(required_role: str):
    """
    Decorador para requerir un rol específico
    """
    def role_checker(current_user: dict = Depends(get_current_active_user)) -> dict:
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """
    Endpoint para login de usuarios
    """
    try:
        user = authenticate_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]},
            expires_delta=access_token_expires
        )

        logger.info(f"User {user['username']} logged in successfully")

        return LoginResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_info={
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """
    Endpoint para logout (en implementación real, invalidar token)
    """
    logger.info(f"User {current_user['username']} logged out")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
async def read_users_me(current_user: dict = Depends(get_current_active_user)):
    """
    Obtiene información del usuario actual
    """
    return User(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user.get("created_at")
    )


@router.post("/register", response_model=User)
async def register_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_role("admin"))
):
    """
    Registra un nuevo usuario (solo admins)
    """
    try:
        # Verificar si el usuario ya existe
        if user_data.username in fake_users_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

        # Hash de la contraseña
        hashed_password, salt = hash_password(user_data.password)

        # Crear nuevo usuario
        user_id = generate_secure_token(8)
        new_user = {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "role": user_data.role,
            "hashed_password": hashed_password,
            "salt": salt,
            "is_active": True,
            "created_at": datetime.utcnow()
        }

        # Guardar en la "base de datos"
        fake_users_db[user_data.username] = new_user

        logger.info(f"New user {user_data.username} registered by {current_user['username']}")

        return User(
            id=new_user["id"],
            username=new_user["username"],
            email=new_user["email"],
            full_name=new_user["full_name"],
            role=new_user["role"],
            is_active=new_user["is_active"],
            created_at=new_user["created_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )


@router.get("/users", response_model=list[User])
async def list_users(
    current_user: dict = Depends(require_role("admin")),
    skip: int = 0,
    limit: int = 100
):
    """
    Lista todos los usuarios (solo admins)
    """
    users = []
    for user_data in list(fake_users_db.values())[skip:skip + limit]:
        users.append(User(
            id=user_data["id"],
            username=user_data["username"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            role=user_data["role"],
            is_active=user_data["is_active"],
            created_at=user_data.get("created_at")
        ))

    return users


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user: dict = Depends(require_role("admin"))
):
    """
    Actualiza el estado activo/inactivo de un usuario (solo admins)
    """
    # Encontrar usuario por ID
    target_user = None
    for user_data in fake_users_db.values():
        if user_data["id"] == user_id:
            target_user = user_data
            break

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    target_user["is_active"] = is_active

    logger.info(f"User {target_user['username']} status updated to {'active' if is_active else 'inactive'} by {current_user['username']}")

    return {"message": f"User status updated successfully"}


@router.get("/validate-token")
async def validate_token(current_user: dict = Depends(get_current_active_user)):
    """
    Valida si un token es válido y retorna información básica del usuario
    """
    return {
        "valid": True,
        "user": {
            "username": current_user["username"],
            "role": current_user["role"]
        }
    }