import os
from fastapi import FastAPI, Depends, HTTPException, status, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
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
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    return payload

def role_required(allowed_roles):
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Permission insuffisante. Rôle requis: {allowed_roles}")
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
    db.refresh(db_user)
    return {"message": "Utilisateur créé avec succès", "user_id": db_user.id, "role": db_user.role_id}

@app.post("/api/auth/login")
async def login(login: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == login.email).first()
    if not user or not verify_password(login.mot_de_passe, user.mot_de_passe):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    
    token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role_id})
    
    # Log login
    log = AuditLog(user_id=user.id, action="LOGIN", details="Connexion réussie", ip_address=request.client.host)
    db.add(log)
    db.commit()
    
    return {"access_token": token, "token_type": "bearer", "role": user.role_id, "user_id": user.id, "nom": user.nom}

# Dashboard endpoints
@app.get("/api/dashboard/dg")
async def dashboard_dg(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    entrees = db.query(Transaction).filter(Transaction.type == "entrée", Transaction.statut == TransactionStatus.APPROUVE).all()
    sorties = db.query(Transaction).filter(Transaction.type == "sortie", Transaction.statut == TransactionStatus.APPROUVE).all()
    
    total_entrees = sum(t.montant for t in entrees)
    total_sorties = sum(t.montant for t in sorties)
    montant_disponible = total_entrees - total_sorties
    
    # Stock quantities
    stocks = db.query(Stock).all()
    quantite_entree = sum(s.quantite_entree for s in stocks)
    quantite_sortie = sum(s.quantite_sortie for s in stocks)
    quantite_disponible = sum(s.quantite_disponible for s in stocks)
    
    en_attente = db.query(Transaction).filter(Transaction.statut == TransactionStatus.EN_ATTENTE).count()
    
    return {
        "total_entrees": total_entrees,
        "total_sorties": total_sorties,
        "montant_disponible": montant_disponible,
        "quantite_entree": quantite_entree,
        "quantite_sortie": quantite_sortie,
        "quantite_disponible": quantite_disponible,
        "validations_en_attente": en_attente
    }

@app.get("/api/dashboard/commercial")
async def dashboard_commercial(current_user = Depends(role_required([RoleEnum.DIRECTEUR_COMMERCIAL])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).all()
    quantite_vendue = sum(v.quantite for v in ventes)
    
    stocks = db.query(Stock).all()
    quantite_disponible = sum(s.quantite_disponible for s in stocks)
    
    # Performance par agent
    agents = db.query(User).filter(User.role_id == RoleEnum.AGENT_MARKETING).all()
    performance = []
    for agent in agents:
        ventes_agent = db.query(Vente).filter(Vente.agent_id == agent.id).all()
        if ventes_agent:
            performance.append({
                "agent": agent.nom,
                "ventes": len(ventes_agent),
                "quantite": sum(v.quantite for v in ventes_agent),
                "montant": sum(v.quantite * v.prix_unitaire for v in ventes_agent)
            })
    
    return {
        "quantite_vendue": quantite_vendue,
        "quantite_disponible": quantite_disponible,
        "performance_agents": performance
    }

# Transaction endpoints
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
    db.refresh(db_transaction)
    
    return {
        "message": "Transaction enregistrée",
        "transaction_id": db_transaction.id,
        "statut": "EN_ATTENTE" if transaction.type == "sortie" else "APPROUVE"
    }

@app.get("/api/transactions/pending")
async def get_pending_transactions(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    pending = db.query(Transaction).filter(Transaction.statut == TransactionStatus.EN_ATTENTE).order_by(Transaction.date.desc()).all()
    return [
        {"id": t.id, "type": t.type, "montant": t.montant, "libelle": t.libelle, "date": t.date.isoformat() if t.date else None}
        for t in pending
    ]

@app.post("/api/transactions/approve")
async def approve_transaction(approve: TransactionApprove, current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == approve.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction non trouvée")
    
    if approve.approuver:
        transaction.statut = TransactionStatus.APPROUVE
        transaction.valide_par = current_user.get("user_id")
        message = "Transaction approuvée avec succès"
    else:
        transaction.statut = TransactionStatus.REJETE
        message = "Transaction rejetée"
    
    db.commit()
    return {"message": message, "transaction_id": transaction.id, "statut": transaction.statut}

@app.get("/api/transactions/history")
async def get_transactions_history(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF, RoleEnum.COMPTABLE])), db: Session = Depends(get_db), limit: int = 100):
    transactions = db.query(Transaction).order_by(Transaction.date.desc()).limit(limit).all()
    return [
        {"id": t.id, "type": t.type, "montant": t.montant, "libelle": t.libelle, "statut": t.statut, "date": t.date.isoformat() if t.date else None}
        for t in transactions
    ]

# Vente endpoints
@app.post("/api/ventes")
async def create_vente(vente: VenteCreate, current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    user_id = current_user.get("user_id")
    
    db_vente = Vente(
        produit=vente.produit,
        quantite=vente.quantite,
        prix_unitaire=vente.prix_unitaire,
        agent_id=user_id
    )
    db.add(db_vente)
    
    # Update stock
    stock = db.query(Stock).filter(Stock.produit == vente.produit).first()
    if stock:
        stock.quantite_sortie += vente.quantite
        stock.quantite_disponible = stock.quantite_entree - stock.quantite_sortie
    else:
        stock = Stock(produit=vente.produit, quantite_sortie=vente.quantite, quantite_disponible=-vente.quantite)
        db.add(stock)
    
    db.commit()
    
    return {"message": "Vente enregistrée avec succès", "produit": vente.produit, "quantite": vente.quantite, "prix_unitaire": vente.prix_unitaire}

@app.get("/api/ventes/my")
async def get_my_ventes(current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    user_id = current_user.get("user_id")
    ventes = db.query(Vente).filter(Vente.agent_id == user_id).order_by(Vente.date.desc()).all()
    return [
        {"id": v.id, "produit": v.produit, "quantite": v.quantite, "prix_unitaire": v.prix_unitaire, "date": v.date.isoformat() if v.date else None}
        for v in ventes
    ]

@app.get("/api/ventes/commercial")
async def get_all_ventes_commercial(current_user = Depends(role_required([RoleEnum.DIRECTEUR_COMMERCIAL])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).order_by(Vente.date.desc()).all()
    return [
        {"id": v.id, "produit": v.produit, "quantite": v.quantite, "prix_unitaire": v.prix_unitaire, "montant_total": v.quantite * v.prix_unitaire, "agent_id": v.agent_id, "date": v.date.isoformat() if v.date else None}
        for v in ventes
    ]

# User management (DG only)
@app.post("/api/users/create")
async def create_user(user: UserCreate, current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    hashed = get_password_hash(user.mot_de_passe)
    db_user = User(nom=user.nom, email=user.email, mot_de_passe=hashed, role_id=user.role)
    db.add(db_user)
    db.commit()
    
    return {"message": f"Utilisateur {user.nom} créé avec succès", "user_id": db_user.id}

@app.post("/api/users/disable/{user_id}")
async def disable_user(user_id: int, current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db)):
    if current_user.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous désactiver vous-même")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    
    user.is_active = False
    db.commit()
    
    return {"message": f"Utilisateur {user.nom} désactivé avec succès"}

@app.get("/api/users/all")
async def get_all_users(current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {"id": u.id, "nom": u.nom, "email": u.email, "role": u.role_id, "active": u.is_active, "created_at": u.created_at.isoformat() if u.created_at else None}
        for u in users
    ]

@app.get("/api/audit-logs")
async def get_audit_logs(current_user = Depends(role_required([RoleEnum.DG])), db: Session = Depends(get_db), limit: int = 100):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {"id": log.id, "user_id": log.user_id, "action": log.action, "details": log.details, "ip_address": log.ip_address, "timestamp": log.timestamp.isoformat() if log.timestamp else None}
        for log in logs
    ]

@app.post("/api/stock/add")
async def add_stock(produit: str, quantite: int, current_user = Depends(role_required([RoleEnum.COMPTABLE, RoleEnum.DG])), db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.produit == produit).first()
    if stock:
        stock.quantite_entree += quantite
        stock.quantite_disponible = stock.quantite_entree - stock.quantite_sortie
    else:
        stock = Stock(produit=produit, quantite_entree=quantite, quantite_disponible=quantite)
        db.add(stock)
    
    db.commit()
    return {"message": f"Stock mis à jour: {produit} +{quantite}"}

@app.get("/api/stock/all")
async def get_all_stocks(current_user = Depends(role_required([RoleEnum.DIRECTEUR_COMMERCIAL, RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    stocks = db.query(Stock).all()
    return [
        {"produit": s.produit, "quantite_entree": s.quantite_entree, "quantite_sortie": s.quantite_sortie, "quantite_disponible": s.quantite_disponible}
        for s in stocks
    ]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
