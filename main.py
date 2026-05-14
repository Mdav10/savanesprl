import os
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import enum

# Database URL - YOUR EXACT DATABASE
DATABASE_URL = "postgresql://mlw_attack_user:ShJf3c9NA4Jf1ADITLYh3fIlHc7akHXC@dpg-d8063p9j2pic73f1mm40-a/mlw_attack"

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-123456789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Database setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Enums
class RoleEnum(str, enum.Enum):
    DG = "DG"
    DAF = "DAF"
    DIRECTEUR_COMMERCIAL = "DIRECTEUR_COMMERCIAL"
    COMPTABLE = "COMPTABLE"
    AGENT_MARKETING = "AGENT_MARKETING"

class TransactionStatus(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    APPROUVE = "APPROUVE"
    REJETE = "REJETE"

# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    mot_de_passe = Column(String(255), nullable=False)
    role_id = Column(Enum(RoleEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    type = Column(String(20), nullable=False)
    montant = Column(Float, nullable=False)
    libelle = Column(String(200), nullable=False)
    statut = Column(Enum(TransactionStatus), default=TransactionStatus.EN_ATTENTE)
    valide_par = Column(Integer, ForeignKey("users.id"), nullable=True)
    date = Column(DateTime, default=datetime.utcnow)

class Vente(Base):
    __tablename__ = "ventes"
    id = Column(Integer, primary_key=True)
    produit = Column(String(100), nullable=False)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    agent_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)

class Stock(Base):
    __tablename__ = "stock"
    id = Column(Integer, primary_key=True)
    produit = Column(String(100), unique=True, nullable=False)
    quantite_entree = Column(Integer, default=0)
    quantite_sortie = Column(Integer, default=0)
    quantite_disponible = Column(Integer, default=0)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(200))
    details = Column(Text)
    ip_address = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)

# Pydantic models
class UserCreate(BaseModel):
    nom: str
    email: EmailStr
    mot_de_passe: str
    role: RoleEnum

class UserLogin(BaseModel):
    email: EmailStr
    mot_de_passe: str

class TransactionCreate(BaseModel):
    type: str
    montant: float
    libelle: str

class VenteCreate(BaseModel):
    produit: str
    quantite: int
    prix_unitaire: float

class TransactionApprove(BaseModel):
    transaction_id: int
    approuver: bool

# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    return payload

def role_required(allowed_roles):
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission insuffisante")
        return current_user
    return role_checker

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create FastAPI app
app = FastAPI(title="SavaneSPRL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup
@app.on_event("startup")
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database error: {e}")

@app.get("/")
def root():
    return {"message": "SavaneSPRL API is running", "status": "healthy"}

@app.get("/health")
def health():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "unhealthy", "error": str(e)})

# Auth endpoints
@app.post("/api/auth/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    hashed = get_password_hash(user.mot_de_passe)
    db_user = User(nom=user.nom, email=user.email, mot_de_passe=hashed, role_id=user.role)
    db.add(db_user)
    db.commit()
    return {"message": "Utilisateur créé", "user_id": db_user.id}

@app.post("/api/auth/login")
async def login(login: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login.email).first()
    if not user or not verify_password(login.mot_de_passe, user.mot_de_passe):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role_id})
    return {"access_token": token, "token_type": "bearer", "role": user.role_id}

@app.get("/api/dashboard/dg")
async def dashboard_dg(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    entrees = db.query(Transaction).filter(Transaction.type == "entrée", Transaction.statut == TransactionStatus.APPROUVE).all()
    sorties = db.query(Transaction).filter(Transaction.type == "sortie", Transaction.statut == TransactionStatus.APPROUVE).all()
    
    return {
        "total_entrees": sum(t.montant for t in entrees),
        "total_sorties": sum(t.montant for t in sorties),
        "montant_disponible": sum(t.montant for t in entrees) - sum(t.montant for t in sorties)
    }

@app.post("/api/transactions")
async def create_transaction(transaction: TransactionCreate, current_user = Depends(role_required([RoleEnum.COMPTABLE])), db: Session = Depends(get_db)):
    db_transaction = Transaction(
        type=transaction.type,
        montant=transaction.montant,
        libelle=transaction.libelle,
        statut=TransactionStatus.EN_ATTENTE if transaction.type == "sortie" else TransactionStatus.APPROUVE
    )
    db.add(db_transaction)
    db.commit()
    return {"message": "Transaction créée", "id": db_transaction.id}

@app.get("/api/transactions/pending")
async def get_pending(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    pending = db.query(Transaction).filter(Transaction.statut == TransactionStatus.EN_ATTENTE).all()
    return pending

@app.post("/api/transactions/approve")
async def approve_transaction(approve: TransactionApprove, current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == approve.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction non trouvée")
    
    transaction.statut = TransactionStatus.APPROUVE if approve.approuver else TransactionStatus.REJETE
    transaction.valide_par = current_user.get("user_id")
    db.commit()
    return {"message": "Transaction approuvée" if approve.approuver else "Transaction rejetée"}

@app.post("/api/ventes")
async def create_vente(vente: VenteCreate, current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    db_vente = Vente(
        produit=vente.produit,
        quantite=vente.quantite,
        prix_unitaire=vente.prix_unitaire,
        agent_id=current_user.get("user_id")
    )
    db.add(db_vente)
    db.commit()
    return {"message": "Vente enregistrée", "quantite": vente.quantite, "prix_unitaire": vente.prix_unitaire}

@app.get("/api/ventes/my")
async def get_my_ventes(current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).filter(Vente.agent_id == current_user.get("user_id")).all()
    return ventes

@app.post("/api/users/create")
async def create_user(user: UserCreate, current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db)):
    hashed = get_password_hash(user.mot_de_passe)
    db_user = User(nom=user.nom, email=user.email, mot_de_passe=hashed, role_id=user.role)
    db.add(db_user)
    db.commit()
    return {"message": f"Utilisateur {user.nom} créé"}

@app.get("/api/users/all")
async def get_all_users(current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "nom": u.nom, "email": u.email, "role": u.role_id} for u in users]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
