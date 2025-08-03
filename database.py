from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from models import Base, Permission, Role, User, user_roles, role_permissions
from passlib.context import CryptContext
from session import Settings
settings = Settings()

# database.py
DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
    f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()
Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def get_session_local():
    return SessionLocal
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    db = SessionLocal()
    try:
        permissions = {
            "read": db.query(Permission).filter_by(name="read").first() or Permission(name="read"),
            "write": db.query(Permission).filter_by(name="write").first() or Permission(name="write"),
            "confirm_courrier": db.query(Permission).filter_by(name="confirm_courrier").first() or Permission(name="confirm_courrier")
        }
        
        roles = {
            "admin": db.query(Role).filter_by(name="admin").first() or Role(name="admin"),
            "user": db.query(Role).filter_by(name="user").first() or Role(name="user"),
            "SUPER": db.query(Role).filter_by(name="SUPER").first() or Role(name="SUPER"),
            "COURIEL": db.query(Role).filter_by(name="COURIEL").first() or Role(name="COURIEL")
        }
        
        roles["admin"].permissions = [permissions["read"], permissions["write"], permissions["confirm_courrier"]]
        roles["user"].permissions = [permissions["read"]]
        roles["SUPER"].permissions = [permissions["read"], permissions["write"]]
        roles["COURIEL"].permissions = [permissions["read"], permissions["confirm_courrier"]]
        
        for obj in [*permissions.values(), *roles.values()]:
            if obj not in db:
                db.add(obj)
        
        db.commit()
        
        if not db.query(User).filter_by(username="admin").first():
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                roles=[roles["admin"]]
            )
            db.add(admin_user)
            db.commit()
            
    except Exception as e:
        db.rollback()
        print(f"Database initialization error: {e}")
    finally:
        db.close()
