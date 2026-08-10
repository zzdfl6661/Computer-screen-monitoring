import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.models import User, Device
from ..auth.schemas import UserCreate, UserLogin, DeviceRegister, DeviceLogin, Token
from ..auth.utils import get_password_hash, verify_password, create_access_token
from logger import setup_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = setup_logger('auth_route')


@router.post("/register", response_model=dict)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用"
        )
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"用户注册成功: {user.username}")
    return {"message": "用户注册成功", "user_id": new_user.id}


@router.post("/login", response_model=Token)
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已禁用"
        )
    
    access_token = create_access_token(data={"sub": db_user.username})
    
    logger.info(f"用户登录成功: {db_user.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/device/register", response_model=dict)
def register_device(device: DeviceRegister, db: Session = Depends(get_db)):
    device_token = str(uuid.uuid4())
    
    new_device = Device(
        device_name=device.device_name,
        device_type=device.device_type,
        device_token=device_token
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    
    logger.info(f"设备注册成功: {device.device_name}")
    return {"message": "设备注册成功", "device_token": device_token}


@router.post("/device/login", response_model=Token)
def login_device(device: DeviceLogin, db: Session = Depends(get_db)):
    db_device = db.query(Device).filter(Device.device_token == device.device_token).first()
    if not db_device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="设备令牌无效"
        )
    
    if not db_device.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="设备已禁用"
        )
    
    access_token = create_access_token(data={"device_token": db_device.device_token})
    
    logger.info(f"设备登录成功: {db_device.device_name}")
    return {"access_token": access_token, "token_type": "bearer"}