from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from db_config import Base

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

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    mot_de_passe = Column(String(255), nullable=False)
    role_id = Column(Enum(RoleEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ventes = relationship("Vente", back_populates="agent")
    logs = relationship("AuditLog", back_populates="user")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    type = Column(String(20), nullable=False)  # entrée/sortie
    montant = Column(Float, nullable=False)
    libelle = Column(String(200), nullable=False)
    statut = Column(Enum(TransactionStatus), default=TransactionStatus.EN_ATTENTE)
    valide_par = Column(Integer, ForeignKey("users.id"), nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    validateur = relationship("User", foreign_keys=[valide_par])

class Vente(Base):
    __tablename__ = "ventes"
    
    id = Column(Integer, primary_key=True)
    produit = Column(String(100), nullable=False)
    quantite = Column(Integer, nullable=False)
    prix_unitaire = Column(Float, nullable=False)
    agent_id = Column(Integer, ForeignKey("users.id"))
    date = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("User", back_populates="ventes")

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
    
    user = relationship("User", back_populates="logs")
