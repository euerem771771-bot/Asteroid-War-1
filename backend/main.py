import os, hashlib, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import subprocess, sys
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from jose import jwt, JWTError
from sqlalchemy import create_engine, String, Integer, select, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.exc import IntegrityError
url=os.getenv("DATABASE_URL","sqlite:///./jogonave.db")
if url.startswith(("postgres://","postgresql://")): url="postgresql+psycopg://"+url.split("://",1)[1]
engine=create_engine(url,connect_args={"check_same_thread":False} if url.startswith("sqlite") else {},pool_pre_ping=True)
Session=sessionmaker(bind=engine)
secret=os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
class Base(DeclarativeBase): pass
class Player(Base):
    __tablename__="players"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    username: Mapped[str]=mapped_column(String(30),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(256))
    record: Mapped[int]=mapped_column(Integer,default=0)
class Device(Base):
    __tablename__="registration_devices"
    key: Mapped[str]=mapped_column(String(64),primary_key=True)
    player_id: Mapped[int]=mapped_column(Integer,index=True)
Base.metadata.create_all(engine)
app=FastAPI(title="Asteroid War")
security=HTTPBearer(auto_error=False)
class Credentials(BaseModel):
    username:str=Field(min_length=3,max_length=30,pattern=r"^[A-Za-z0-9_]+$")
    password:str=Field(min_length=8,max_length=100)
class Registration(Credentials):
    device_id:str=Field(min_length=16,max_length=128)
class DeleteAccount(BaseModel):
    password:str=Field(min_length=8,max_length=100)
class Score(BaseModel):
    score:int=Field(ge=0,le=100000000)
def hashpw(p,s=None):
    s=s or secrets.token_hex(16)
    return s+"$"+hashlib.pbkdf2_hmac("sha256",p.encode(),bytes.fromhex(s),310000).hex()
def info(p): return {"id":p.id,"username":p.username,"record":p.record}
def auth(p): return {"token":jwt.encode({"sub":str(p.id),"exp":datetime.now(timezone.utc)+timedelta(days=30)},secret,algorithm="HS256"),"player":info(p)}
def player_id(c:HTTPAuthorizationCredentials=Depends(security)):
    try: return int(jwt.decode(c.credentials,secret,algorithms=["HS256"])["sub"])
    except (AttributeError,JWTError,ValueError,KeyError): raise HTTPException(401,"Faça login novamente.")
@app.get("/")
def home(): return RedirectResponse("/school/")

school_dir = Path(__file__).resolve().parent / "school_game"
@app.on_event("startup")
def build_school_game():
    output = school_dir / "build" / "web"
    if not (output / "index.html").exists():
        subprocess.run([sys.executable, "-m", "pygbag", "--build", str(school_dir)], check=True, timeout=180)
    app.mount("/school", StaticFiles(directory=output, html=True), name="school")
@app.get("/health")
def health(): return {"status":"online"}
@app.post("/register")
def register(d:Registration):
    with Session() as db:
        key=hashlib.sha256(d.device_id.encode()).hexdigest()
        if db.get(Device,key): raise HTTPException(409,"Este navegador já cadastrou uma conta.")
        p=Player(username=d.username,password_hash=hashpw(d.password),record=0)
        db.add(p)
        try:
            db.flush()
            db.add(Device(key=key,player_id=p.id))
            db.commit()
        except IntegrityError: raise HTTPException(409,"Usuário ou navegador já cadastrado.")
        return auth(p)
@app.post("/login")
def login(d:Credentials):
    with Session() as db:
        p=db.scalar(select(Player).where(Player.username==d.username))
        if not p or not secrets.compare_digest(p.password_hash,hashpw(d.password,p.password_hash.split("$")[0])): raise HTTPException(401,"Usuário ou senha incorretos.")
        return auth(p)
@app.get("/me")
def me(i=Depends(player_id)):
    with Session() as db:
        p=db.get(Player,i)
        if not p: raise HTTPException(401,"Jogador não encontrado.")
        return info(p)
@app.get("/ranking")
def ranking():
    with Session() as db: return [{"username":p.username,"record":p.record} for p in db.scalars(select(Player).order_by(desc(Player.record),Player.username).limit(10))]
@app.post("/score")
def score(d:Score,i=Depends(player_id)):
    with Session() as db:
        p=db.get(Player,i)
        if not p: raise HTTPException(401,"Jogador não encontrado.")
        p.record=max(p.record,d.score)
        db.commit()
        return {"record":p.record}

@app.post("/delete-account")
def delete_account(d:DeleteAccount,i=Depends(player_id)):
    with Session() as db:
        p=db.get(Player,i)
        if not p or not secrets.compare_digest(p.password_hash,hashpw(d.password,p.password_hash.split("$")[0])): raise HTTPException(401,"Senha incorreta.")
        for device in db.scalars(select(Device).where(Device.player_id==i)):
            db.delete(device)
        db.delete(p)
        db.commit()
        return {"deleted":True}
