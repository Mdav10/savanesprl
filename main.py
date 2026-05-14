import os
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

# Database URL
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
app = FastAPI(title="SavaneSPRL Financial System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML Interface
HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SavaneSPRL - Système Financier</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .header h1 {
            color: #333;
            font-size: 28px;
        }
        .header p {
            color: #666;
            margin-top: 5px;
        }
        .login-box, .dashboard {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .card h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .stat-box h4 {
            font-size: 14px;
            margin-bottom: 10px;
            opacity: 0.9;
        }
        .stat-box .value {
            font-size: 28px;
            font-weight: bold;
        }
        .transaction-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .transaction-item {
            background: white;
            padding: 10px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .alert {
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .nav-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .badge {
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
        }
        .logout-btn {
            background: #dc3545;
            padding: 8px 20px;
        }
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .stats {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏦 SavaneSPRL</h1>
            <p>Système de Gestion Financière Sécurisé</p>
        </div>

        <!-- Login Section -->
        <div id="loginSection" class="login-box">
            <h2>🔐 Connexion</h2>
            <div id="loginAlert"></div>
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="email" placeholder="exemple@entreprise.com">
            </div>
            <div class="form-group">
                <label>Mot de passe</label>
                <input type="password" id="password" placeholder="Votre mot de passe">
            </div>
            <button onclick="login()">Se connecter</button>
            <div style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 8px;">
                <h4>📝 Comptes de test:</h4>
                <p><strong>DG:</strong> dg@savane.com / Admin123!</p>
                <p><strong>DAF:</strong> daf@savane.com / Admin123!</p>
                <p><strong>Comptable:</strong> comptable@savane.com / Admin123!</p>
                <p><strong>Agent:</strong> agent@savane.com / Admin123!</p>
            </div>
        </div>

        <!-- Dashboard Section -->
        <div id="dashboardSection" style="display:none;">
            <div class="nav-bar">
                <h2>📊 Tableau de Bord</h2>
                <div class="user-info">
                    <span id="userRole" class="badge"></span>
                    <span id="userName"></span>
                    <button onclick="logout()" class="logout-btn">Déconnexion</button>
                </div>
            </div>
            
            <div id="dashboardContent"></div>
        </div>
    </div>

    <script>
        const API_URL = window.location.origin;
        let authToken = localStorage.getItem('token');
        let userRole = localStorage.getItem('role');

        if(authToken) {
            document.getElementById('loginSection').style.display = 'none';
            document.getElementById('dashboardSection').style.display = 'block';
            loadDashboard();
        }

        async function login() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            try {
                const response = await fetch(`${API_URL}/api/auth/login`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, mot_de_passe: password})
                });
                const data = await response.json();
                
                if(response.ok) {
                    authToken = data.access_token;
                    userRole = data.role;
                    localStorage.setItem('token', authToken);
                    localStorage.setItem('role', userRole);
                    localStorage.setItem('userEmail', email);
                    
                    document.getElementById('loginSection').style.display = 'none';
                    document.getElementById('dashboardSection').style.display = 'block';
                    loadDashboard();
                } else {
                    showAlert('loginAlert', 'Échec de connexion: ' + JSON.stringify(data), 'error');
                }
            } catch(error) {
                showAlert('loginAlert', 'Erreur: ' + error.message, 'error');
            }
        }

        function logout() {
            localStorage.clear();
            location.reload();
        }

        async function loadDashboard() {
            document.getElementById('userRole').innerText = userRole;
            document.getElementById('userName').innerText = localStorage.getItem('userEmail');
            
            if(userRole === 'DG' || userRole === 'DAF') {
                await loadDGDashboard();
            } else if(userRole === 'DIRECTEUR_COMMERCIAL') {
                await loadCommercialDashboard();
            } else if(userRole === 'COMPTABLE') {
                await loadComptableDashboard();
            } else if(userRole === 'AGENT_MARKETING') {
                await loadAgentDashboard();
            }
        }

        async function loadDGDashboard() {
            try {
                const response = await fetch(`${API_URL}/api/dashboard/dg`, {
                    headers: {'Authorization': `Bearer ${authToken}`}
                });
                const data = await response.json();
                
                const html = `
                    <div class="stats">
                        <div class="stat-box">
                            <h4>💰 Total Entrées</h4>
                            <div class="value">${data.total_entrees?.toLocaleString() || 0} FCFA</div>
                        </div>
                        <div class="stat-box">
                            <h4>💸 Total Sorties</h4>
                            <div class="value">${data.total_sorties?.toLocaleString() || 0} FCFA</div>
                        </div>
                        <div class="stat-box">
                            <h4>📊 Montant Disponible</h4>
                            <div class="value">${data.montant_disponible?.toLocaleString() || 0} FCFA</div>
                        </div>
                        <div class="stat-box">
                            <h4>⏳ Validations en Attente</h4>
                            <div class="value">${data.validations_en_attente || 0}</div>
                        </div>
                    </div>
                    
                    <div class="grid">
                        <div class="card">
                            <h3>📦 Gestion des Stocks</h3>
                            <p><strong>Quantité Entrée:</strong> ${data.quantite_entree || 0}</p>
                            <p><strong>Quantité Sortie:</strong> ${data.quantite_sortie || 0}</p>
                            <p><strong>Quantité Disponible:</strong> ${data.quantite_disponible || 0}</p>
                        </div>
                        <div class="card">
                            <h3>👥 Gestion des Utilisateurs</h3>
                            <button onclick="listUsers()">Liste des utilisateurs</button>
                            <div id="userList"></div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>✅ Transactions en Attente</h3>
                        <div id="pendingTransactions"></div>
                    </div>
                `;
                document.getElementById('dashboardContent').innerHTML = html;
                loadPendingTransactions();
            } catch(error) {
                console.error(error);
            }
        }

        async function loadPendingTransactions() {
            try {
                const response = await fetch(`${API_URL}/api/transactions/pending`, {
                    headers: {'Authorization': `Bearer ${authToken}`}
                });
                const transactions = await response.json();
                
                let html = '<div class="transaction-list">';
                for(const t of transactions) {
                    html += `
                        <div class="transaction-item">
                            <strong>${t.libelle}</strong><br>
                            Montant: ${t.montant.toLocaleString()} FCFA<br>
                            Type: ${t.type}<br>
                            <button onclick="approveTransaction(${t.id}, true)">✅ Approuver</button>
                            <button onclick="approveTransaction(${t.id}, false)">❌ Rejeter</button>
                        </div>
                    `;
                }
                html += '</div>';
                document.getElementById('pendingTransactions').innerHTML = html || 'Aucune transaction en attente';
            } catch(error) {
                console.error(error);
            }
        }

        async function loadComptableDashboard() {
            const html = `
                <div class="card">
                    <h3>💰 Nouvelle Transaction</h3>
                    <div class="form-group">
                        <label>Type</label>
                        <select id="transType">
                            <option value="entrée">Entrée (Revenu)</option>
                            <option value="sortie">Sortie (Dépense - Nécessite validation)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Montant (FCFA)</label>
                        <input type="number" id="montant">
                    </div>
                    <div class="form-group">
                        <label>Libellé</label>
                        <input type="text" id="libelle" placeholder="Description">
                    </div>
                    <button onclick="createTransaction()">Enregistrer</button>
                </div>
                <div class="card">
                    <h3>📜 Historique des Transactions</h3>
                    <button onclick="loadTransactionHistory()">Voir l'historique</button>
                    <div id="historyList"></div>
                </div>
            `;
            document.getElementById('dashboardContent').innerHTML = html;
        }

        async function loadAgentDashboard() {
            const html = `
                <div class="card">
                    <h3>📦 Enregistrer une Vente</h3>
                    <div class="form-group">
                        <label>Produit</label>
                        <input type="text" id="produit" placeholder="Nom du produit">
                    </div>
                    <div class="form-group">
                        <label>Quantité</label>
                        <input type="number" id="quantite">
                    </div>
                    <div class="form-group">
                        <label>Prix Unitaire (FCFA)</label>
                        <input type="number" id="prixUnitaire">
                    </div>
                    <button onclick="createVente()">Enregistrer la vente</button>
                </div>
                <div class="card">
                    <h3>📋 Mes Ventes</h3>
                    <button onclick="loadMyVentes()">Voir mes ventes</button>
                    <div id="ventesList"></div>
                </div>
            `;
            document.getElementById('dashboardContent').innerHTML = html;
        }

        async function loadCommercialDashboard() {
            try {
                const response = await fetch(`${API_URL}/api/dashboard/commercial`, {
                    headers: {'Authorization': `Bearer ${authToken}`}
                });
                const data = await response.json();
                
                let performanceHtml = '';
                for(const agent of data.performance_agents || []) {
                    performanceHtml += `
                        <div class="transaction-item">
                            <strong>${agent.agent}</strong><br>
                            Ventes: ${agent.ventes} | Quantité: ${agent.quantite} | Montant: ${agent.montant?.toLocaleString()} FCFA
                        </div>
                    `;
                }
                
                const html = `
                    <div class="stats">
                        <div class="stat-box">
                            <h4>📦 Quantité Vendue</h4>
                            <div class="value">${data.quantite_vendue || 0}</div>
                        </div>
                        <div class="stat-box">
                            <h4>📊 Quantité Disponible</h4>
                            <div class="value">${data.quantite_disponible || 0}</div>
                        </div>
                    </div>
                    <div class="card">
                        <h3>📈 Performance des Agents</h3>
                        ${performanceHtml || 'Aucune donnée'}
                    </div>
                    <div class="card">
                        <h3>📋 Toutes les Ventes</h3>
                        <button onclick="loadAllVentes()">Voir toutes les ventes</button>
                        <div id="allVentesList"></div>
                    </div>
                `;
                document.getElementById('dashboardContent').innerHTML = html;
            } catch(error) {
                console.error(error);
            }
        }

        // API Functions
        async function createTransaction() {
            const type = document.getElementById('transType').value;
            const montant = parseFloat(document.getElementById('montant').value);
            const libelle = document.getElementById('libelle').value;
            
            const response = await fetch(`${API_URL}/api/transactions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({type, montant, libelle})
            });
            const data = await response.json();
            alert(JSON.stringify(data));
            if(response.ok) loadDashboard();
        }

        async function createVente() {
            const produit = document.getElementById('produit').value;
            const quantite = parseInt(document.getElementById('quantite').value);
            const prix_unitaire = parseFloat(document.getElementById('prixUnitaire').value);
            
            const response = await fetch(`${API_URL}/api/ventes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({produit, quantite, prix_unitaire})
            });
            const data = await response.json();
            alert(JSON.stringify(data));
        }

        async function approveTransaction(id, approuver) {
            const response = await fetch(`${API_URL}/api/transactions/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({transaction_id: id, approuver})
            });
            const data = await response.json();
            alert(JSON.stringify(data));
            loadDashboard();
        }

        async function listUsers() {
            const response = await fetch(`${API_URL}/api/users/all`, {
                headers: {'Authorization': `Bearer ${authToken}`}
            });
            const users = await response.json();
            let html = '<div class="transaction-list">';
            for(const u of users) {
                html += `<div class="transaction-item">${u.nom} - ${u.email} - ${u.role}</div>`;
            }
            html += '</div>';
            document.getElementById('userList').innerHTML = html;
        }

        function showAlert(elementId, message, type) {
            const alertDiv = document.getElementById(elementId);
            alertDiv.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            setTimeout(() => alertDiv.innerHTML = '', 5000);
        }

        window.approveTransaction = approveTransaction;
        window.listUsers = listUsers;
        window.createTransaction = createTransaction;
        window.createVente = createVente;
        window.loadMyVentes = async () => {
            const response = await fetch(`${API_URL}/api/ventes/my`, {
                headers: {'Authorization': `Bearer ${authToken}`}
            });
            const ventes = await response.json();
            let html = '<div class="transaction-list">';
            for(const v of ventes) {
                html += `<div class="transaction-item">${v.produit} - ${v.quantite} x ${v.prix_unitaire} FCFA</div>`;
            }
            html += '</div>';
            document.getElementById('ventesList').innerHTML = html;
        };
        window.loadAllVentes = async () => {
            const response = await fetch(`${API_URL}/api/ventes/commercial`, {
                headers: {'Authorization': `Bearer ${authToken}`}
            });
            const ventes = await response.json();
            let html = '<div class="transaction-list">';
            for(const v of ventes) {
                html += `<div class="transaction-item">${v.produit} - ${v.quantite} x ${v.prix_unitaire} = ${v.montant_total} FCFA (Agent: ${v.agent_id})</div>`;
            }
            html += '</div>';
            document.getElementById('allVentesList').innerHTML = html;
        };
        window.loadTransactionHistory = async () => {
            const response = await fetch(`${API_URL}/api/transactions/history`, {
                headers: {'Authorization': `Bearer ${authToken}`}
            });
            const transactions = await response.json();
            let html = '<div class="transaction-list">';
            for(const t of transactions) {
                html += `<div class="transaction-item">${t.libelle} - ${t.montant} FCFA - ${t.statut}</div>`;
            }
            html += '</div>';
            document.getElementById('historyList').innerHTML = html;
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    return HTMLResponse(HTML_PAGE)

# Create tables on startup
@app.on_event("startup")
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"⚠️ Database error: {e}")

@app.get("/health")
def health():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "unhealthy", "error": str(e)})

# API Endpoints (keep all your existing endpoints)
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
    return {"access_token": token, "token_type": "bearer", "role": user.role_id, "user_id": user.id, "nom": user.nom}

@app.get("/api/dashboard/dg")
async def dashboard_dg(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    entrees = db.query(Transaction).filter(Transaction.type == "entrée", Transaction.statut == TransactionStatus.APPROUVE).all()
    sorties = db.query(Transaction).filter(Transaction.type == "sortie", Transaction.statut == TransactionStatus.APPROUVE).all()
    stocks = db.query(Stock).all()
    return {
        "total_entrees": sum(t.montant for t in entrees),
        "total_sorties": sum(t.montant for t in sorties),
        "montant_disponible": sum(t.montant for t in entrees) - sum(t.montant for t in sorties),
        "quantite_entree": sum(s.quantite_entree for s in stocks),
        "quantite_sortie": sum(s.quantite_sortie for s in stocks),
        "quantite_disponible": sum(s.quantite_disponible for s in stocks),
        "validations_en_attente": db.query(Transaction).filter(Transaction.statut == TransactionStatus.EN_ATTENTE).count()
    }

@app.get("/api/dashboard/commercial")
async def dashboard_commercial(current_user = Depends(role_required([RoleEnum.DIRECTEUR_COMMERCIAL])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).all()
    stocks = db.query(Stock).all()
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
        "quantite_vendue": sum(v.quantite for v in ventes),
        "quantite_disponible": sum(s.quantite_disponible for s in stocks),
        "performance_agents": performance
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
    return {"message": "Transaction créée", "id": db_transaction.id, "statut": db_transaction.statut}

@app.get("/api/transactions/pending")
async def get_pending(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    pending = db.query(Transaction).filter(Transaction.statut == TransactionStatus.EN_ATTENTE).all()
    return [{"id": t.id, "type": t.type, "montant": t.montant, "libelle": t.libelle} for t in pending]

@app.post("/api/transactions/approve")
async def approve_transaction(approve: TransactionApprove, current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF])), db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == approve.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction non trouvée")
    transaction.statut = TransactionStatus.APPROUVE if approve.approuver else TransactionStatus.REJETE
    db.commit()
    return {"message": "Transaction approuvée" if approve.approuver else "Transaction rejetée"}

@app.get("/api/transactions/history")
async def get_history(current_user = Depends(role_required([RoleEnum.DG, RoleEnum.DAF, RoleEnum.COMPTABLE])), db: Session = Depends(get_db)):
    transactions = db.query(Transaction).order_by(Transaction.date.desc()).limit(50).all()
    return [{"id": t.id, "libelle": t.libelle, "montant": t.montant, "type": t.type, "statut": t.statut} for t in transactions]

@app.post("/api/ventes")
async def create_vente(vente: VenteCreate, current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    db_vente = Vente(produit=vente.produit, quantite=vente.quantite, prix_unitaire=vente.prix_unitaire, agent_id=current_user.get("user_id"))
    db.add(db_vente)
    stock = db.query(Stock).filter(Stock.produit == vente.produit).first()
    if stock:
        stock.quantite_sortie += vente.quantite
        stock.quantite_disponible = stock.quantite_entree - stock.quantite_sortie
    else:
        stock = Stock(produit=vente.produit, quantite_sortie=vente.quantite, quantite_disponible=-vente.quantite)
        db.add(stock)
    db.commit()
    return {"message": "Vente enregistrée"}

@app.get("/api/ventes/my")
async def get_my_ventes(current_user = Depends(role_required([RoleEnum.AGENT_MARKETING])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).filter(Vente.agent_id == current_user.get("user_id")).all()
    return [{"id": v.id, "produit": v.produit, "quantite": v.quantite, "prix_unitaire": v.prix_unitaire} for v in ventes]

@app.get("/api/ventes/commercial")
async def get_all_ventes(current_user = Depends(role_required([RoleEnum.DIRECTEUR_COMMERCIAL])), db: Session = Depends(get_db)):
    ventes = db.query(Vente).all()
    return [{"id": v.id, "produit": v.produit, "quantite": v.quantite, "prix_unitaire": v.prix_unitaire, "montant_total": v.quantite * v.prix_unitaire, "agent_id": v.agent_id} for v in ventes]

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
