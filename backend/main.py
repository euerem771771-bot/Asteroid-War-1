import os, hashlib, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse
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
class Wallet(Base):
    __tablename__="cosmetic_wallets"
    player_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    spent: Mapped[int]=mapped_column(Integer,default=0)
    owned: Mapped[str]=mapped_column(String(2000),default="")
    ship: Mapped[str]=mapped_column(String(40),default="triangle")
    color: Mapped[str]=mapped_column(String(40),default="gold")
    shot: Mapped[str]=mapped_column(String(40),default="round")
class Gems(Base):
    __tablename__="gem_wallets"
    player_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    balance: Mapped[int]=mapped_column(Integer,default=0)
    claims: Mapped[str]=mapped_column(String(16000),default="")
class Gold(Base):
    __tablename__="gold_balances"
    player_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    balance: Mapped[int]=mapped_column(Integer,default=0)
class PaidRun(Base):
    __tablename__="paid_runs"
    key: Mapped[str]=mapped_column(String(100),primary_key=True)
class Migration(Base):
    __tablename__="game_migrations"
    key: Mapped[str]=mapped_column(String(100),primary_key=True)
Base.metadata.create_all(engine)
with Session() as db:
    if not db.get(Migration,"gold_and_ranking_reset_v1"):
        for p in db.scalars(select(Player)):
            w=db.get(Wallet,p.id)
            db.add(Gold(player_id=p.id,balance=max(0,p.record-(w.spent if w else 0))))
            p.record=0
        db.add(Migration(key="gold_and_ranking_reset_v1"))
        try: db.commit()
        except IntegrityError: db.rollback()

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
    run:str=Field(default="",max_length=64)
def hashpw(p,s=None):
    s=s or secrets.token_hex(16)
    return s+"$"+hashlib.pbkdf2_hmac("sha256",p.encode(),bytes.fromhex(s),310000).hex()
def info(p): return {"id":p.id,"username":p.username,"record":p.record}
def auth(p): return {"token":jwt.encode({"sub":str(p.id),"exp":datetime.now(timezone.utc)+timedelta(days=30)},secret,algorithm="HS256"),"player":info(p)}
def player_id(c:HTTPAuthorizationCredentials=Depends(security)):
    try: return int(jwt.decode(c.credentials,secret,algorithms=["HS256"])["sub"])
    except (AttributeError,JWTError,ValueError,KeyError): raise HTTPException(401,"Faça login novamente.")
@app.get("/")
def home(): return FileResponse(Path(__file__).parent/"index.html")
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
        p=db.scalar(select(Player).where(Player.id==i).with_for_update())
        p.record=max(p.record,d.score)
        key=str(i)+":"+d.run
        if d.run and not db.get(PaidRun,key):
            gold=db.get(Gold,i)
            if not gold:
                gold=Gold(player_id=i,balance=0)
                db.add(gold)
            gold.balance+=d.score//10
            db.add(PaidRun(key=key))
        db.commit()
        return {"record":p.record}

@app.post("/delete-account")
def delete_account(d:DeleteAccount,i=Depends(player_id)):
    with Session() as db:
        p=db.get(Player,i)
        if not p or not secrets.compare_digest(p.password_hash,hashpw(d.password,p.password_hash.split("$")[0])): raise HTTPException(401,"Senha incorreta.")
        for device in db.scalars(select(Device).where(Device.player_id==i)):
            db.delete(device)
        w=db.get(Wallet,i)
        if w: db.delete(w)
        g=db.get(Gems,i)
        if g: db.delete(g)
        gold=db.get(Gold,i)
        if gold: db.delete(gold)
        db.delete(p)
        db.commit()
        return {"deleted":True}

CATALOG={
 "triangle":("ship","Triangular",0),"diamond":("ship","Diamante",500),"pentagon":("ship","Pentagonal",1000),"hexagon":("ship","Hexagonal",1500),"octagon":("ship","Octogonal",2500),
 "gold":("color","Dourado",0),"cyan":("color","Azul",200),"red":("color","Vermelho",200),"purple":("color","Roxo",300),"green":("color","Verde",300),"white":("color","Branco",400),
 "round":("shot","Esfera",0),"beam":("shot","Laser",400),"crystal":("shot","Cristal",600)}
class CosmeticAction(BaseModel):
    item:str
def shop_state(p,w,g=None,gold=None):
    return {"diamonds":g.balance if g else 0,"coins":(gold.balance if gold else 0),"owned":(w.owned.split(",") if w and w.owned else [])+[k for k,v in CATALOG.items() if v[2]==0],"equipped":{"ship":w.ship if w else "triangle","color":w.color if w else "gold","shot":w.shot if w else "round"},"catalog":[{"id":k,"kind":v[0],"name":v[1],"price":v[2],"currency":"diamond" if k in RARE else "gold"} for k,v in CATALOG.items()]}
@app.get("/shop")
def shop(i=Depends(player_id)):
    with Session() as db:
        p=db.get(Player,i)
        if not p: raise HTTPException(401,"Jogador não encontrado.")
        return shop_state(p,db.get(Wallet,i),db.get(Gems,i),db.get(Gold,i))
@app.post("/shop/equip")
def equip(d:CosmeticAction,i=Depends(player_id)):
    item=CATALOG.get(d.item)
    if not item: raise HTTPException(404,"Item inexistente.")
    with Session() as db:
        p=db.scalar(select(Player).where(Player.id==i).with_for_update())
        if not p: raise HTTPException(401,"Jogador não encontrado.")
        w=db.get(Wallet,i)
        if not w:
            w=Wallet(player_id=i,spent=0,owned="",ship="triangle",color="gold",shot="round")
            db.add(w)
        g=db.get(Gems,i)
        gold=db.get(Gold,i)
        owned=set(filter(None,w.owned.split(",")))
        if item[2] and d.item not in owned:
            if d.item in RARE:
                if not g or g.balance<item[2]: raise HTTPException(400,"Diamantes insuficientes.")
                g.balance-=item[2]
            else:
                if not gold or gold.balance<item[2]: raise HTTPException(400,"Moedas insuficientes.")
                gold.balance-=item[2]
            owned.add(d.item)
            w.owned=",".join(sorted(owned))
        setattr(w,item[0],d.item)
        db.commit()
        return shop_state(p,w,g,gold)

# Private multiplayer rooms, single server process.
import time, threading, random
rooms={}
room_lock=threading.RLock()
class Invite(BaseModel):
    username:str
    mode:str
class RoomAction(BaseModel):
    room:str
    action:str
    x:float=Field(default=0.5,ge=0,le=1)
def room_view(r,i):
    other=next(p for p in r["players"] if p!=i)
    return {"id":r["id"],"mode":r["mode"],"status":r["status"],"from":r["names"][r["players"][0]],"to":r["names"][r["players"][1]],"incoming":i==r["players"][1],"hp":r["hp"][i],"opponent_hp":r["hp"][other],"winner":r["winner"],"me":i,"elapsed":max(0,time.monotonic()-r["start"]) if r["start"] else 0,"events":r["events"][i][-80:],"seed":r["seed"]}
@app.get("/multi")
def multi_list(i=Depends(player_id)):
    with room_lock:
        return [room_view(r,i) for r in rooms.values() if i in r["players"] and time.monotonic()-r["created"]<3600]
@app.post("/multi/invite")
def multi_invite(d:Invite,i=Depends(player_id)):
    if d.mode not in ("duel","race"): raise HTTPException(400,"Modo inválido.")
    with Session() as db:
        p=db.get(Player,i)
        q=db.scalar(select(Player).where(Player.username==d.username))
        if not p or not q or p.id==q.id: raise HTTPException(400,"Escolha outro jogador existente.")
        with room_lock:
            now=time.monotonic()
            for k in list(rooms):
                if now-rooms[k]["created"]>3600: del rooms[k]
            if any(i in r["players"] and r["status"] in ("pending","playing") for r in rooms.values()): raise HTTPException(409,"Encerre seu convite ou partida anterior.")
            if len(rooms)>=500: raise HTTPException(503,"Servidor ocupado.")
            k=secrets.token_hex(12)
            r={"id":k,"mode":d.mode,"players":[i,q.id],"names":{i:p.username,q.id:q.username},"status":"pending","hp":{i:200,q.id:200},"x":{i:.5,q.id:.5},"last":{i:0,q.id:0},"special":{i:0,q.id:0},"events":{i:[],q.id:[]},"winner":None,"created":now,"start":0,"seed":random.randrange(1000000)}
            rooms[k]=r
            return room_view(r,i)
@app.post("/multi/action")
def multi_action(d:RoomAction,i=Depends(player_id)):
    with room_lock:
        r=rooms.get(d.room)
        if not r or i not in r["players"]: raise HTTPException(404,"Partida inexistente.")
        other=next(p for p in r["players"] if p!=i)
        now=time.monotonic()
        if d.action=="accept" and r["status"]=="pending" and i==r["players"][1]:
            r["status"]="playing";r["start"]=now
        elif d.action=="leave" and r["status"] in ("pending","playing"):
            r["status"]="finished";r["winner"]=other if r["start"] else None
        elif r["status"]=="playing":
            r["x"][i]=d.x
            if d.action in ("fire","special") and r["mode"]=="duel":
                special=d.action=="special"
                if now-r["last"][i]>=.3 and (not special or now-r["special"][i]>=10):
                    r["last"][i]=now
                    if special:r["special"][i]=now
                    r["events"][other].append({"x":d.x,"special":special,"at":now-r["start"]})
                    r["events"][other]=r["events"][other][-80:]
                    if abs(d.x-r["x"][other])<(.09 if special else .045):
                        r["hp"][other]=max(0,r["hp"][other]-(150 if special else 10))
                        if not r["hp"][other]:r["status"]="finished";r["winner"]=i
            if d.action=="lost" and r["mode"]=="race":
                r["status"]="finished";r["winner"]=other
        return room_view(r,i)

RARE={"nova","prism","pulse"}
CATALOG.update({"nova":("ship","Nova estelar",400),"prism":("color","Prisma violeta",250),"pulse":("shot","Pulso estelar",300)})
class BossClaim(BaseModel):
    run:str=Field(min_length=16,max_length=64,pattern=r"^[a-zA-Z0-9_-]+$")
    stage:int=Field(ge=1,le=100)
@app.post("/boss-reward")
def boss_reward(d:BossClaim,i=Depends(player_id)):
    with Session() as db:
        p=db.scalar(select(Player).where(Player.id==i).with_for_update())
        if not p: raise HTTPException(401,"Jogador inexistente.")
        g=db.get(Gems,i)
        if not g:
            g=Gems(player_id=i,balance=0,claims="")
            db.add(g)
        key=d.run+":"+str(d.stage)
        claims=g.claims.split(",")
        if key not in claims:
            g.balance+=100
            g.claims=",".join((claims+[key])[-200:])
        db.commit()
        return {"diamonds":g.balance}
