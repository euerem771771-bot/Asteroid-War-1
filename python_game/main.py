import asyncio
import math
import random
import pygame

pygame.init()
W,H=1000,700
screen=pygame.display.set_mode((W,H),pygame.RESIZABLE)
pygame.display.set_caption("Asteroid War - Python")
canvas=pygame.Surface((W,H))
clock=pygame.time.Clock()
font=pygame.font.Font(None,30)
big=pygame.font.Font(None,60)
colors=["#ff4545","#42aaff","#ffe24c","#ff8c20","#65eaa0","#c58aff","#f5f5ff"]
names=["DUPLO","VELOZ","PESADO","SUPERNOVA","ESCUDO","AGILIDADE","DANO BOSS"]
stars=[(random.randrange(W),random.randrange(H)) for _ in range(100)]
mode="joystick"
positions=[pygame.Vector2(100,610),pygame.Vector2(900,610)]
touches={}
editing=False
options=False
paused=False
record=0
state="menu"
drag=None
def reset():
    global ship,score,lives,shots,enemies,orbs,hazards,powers,boss,stage,next_power,next_boss,spawn,cool,state,notice,notice_time,paused,options,editing
    ship=pygame.Vector2(500,550)
    score=0
    lives=5
    shots=[]; enemies=[]; orbs=[]; hazards=[]; powers={}
    boss=None
    stage=0; next_power=350; next_boss=2000
    spawn=0; cool=0
    state="play"; notice=""; notice_time=0
    paused=False; options=False; editing=False
    touches.clear()
reset()
state="menu"
def label(s,x,y,color="white",f=font):
    canvas.blit(f.render(str(s),True,color),(x,y))
def button(s,rect):
    pygame.draw.rect(canvas,"#203b54",rect,border_radius=10)
    pygame.draw.rect(canvas,"#65eaa0",rect,2,border_radius=10)
    t=font.render(s,True,"white")
    canvas.blit(t,t.get_rect(center=rect.center))
def poly(pos,r,n,angle=0):
    return [(pos[0]+r*math.cos(angle+i*math.tau/n),pos[1]+r*math.sin(angle+i*math.tau/n)) for i in range(n)]
def damage():
    global lives
    if 4 in powers: del powers[4]
    else: lives-=1
def reward():
    global lives,notice,notice_time
    p=random.choice([4,5,6,7] if lives<5 else [4,5,6])
    if p==7: lives+=1; notice="Presente: +1 vida"
    else: powers[p]=60; notice="Presente: "+names[p]
    notice_time=4
def update(dt):
    global score,lives,boss,stage,next_power,next_boss,spawn,cool,state,record,notice_time
    for p in list(powers):
        powers[p]-=dt
        if powers[p]<=0: del powers[p]
    notice_time=max(0,notice_time-dt)
    keys=pygame.key.get_pressed()
    v=pygame.Vector2(int(keys[pygame.K_RIGHT] or keys[pygame.K_d])-int(keys[pygame.K_LEFT] or keys[pygame.K_a]),int(keys[pygame.K_DOWN] or keys[pygame.K_s])-int(keys[pygame.K_UP] or keys[pygame.K_w]))
    fire=keys[pygame.K_SPACE]
    for p in touches.values():
        delta=p-positions[0]
        if delta.length()<105:
            if mode=="setas":
                if abs(delta.x)>abs(delta.y): v.x+=1 if delta.x>0 else -1
                else: v.y+=1 if delta.y>0 else -1
            else: v+=delta/50
        if p.distance_to(positions[1])<75: fire=True
    if v.length()>1: v.normalize_ip()
    ship.update(max(25,min(W-25,ship.x+v.x*(850 if 5 in powers else 720)*dt)),max(85,min(H-25,ship.y+v.y*(850 if 5 in powers else 720)*dt)))
    cool-=dt
    if fire and cool<=0:
        for off in ([-17,0,17] if 3 in powers else [-12,12] if 0 in powers else [0]):
            shots.append([pygame.Vector2(ship.x+off,ship.y-20),8 if 2 in powers or 3 in powers else 6,690 if 1 in powers or 3 in powers else 540])
        cool=.33 if 0 in powers else .30 if 3 in powers else .25
    if not boss:
        spawn+=dt
        if spawn>=max(.58,1-stage*.07):
            spawn=0; enemies.append(pygame.Vector2(random.randrange(25,W-25),-25))
    for s in shots[:]:
        s[0].y-=s[2]*dt
        if s[0].y<0: shots.remove(s)
    for e in enemies[:]:
        e.y+=min(230,130+stage*12)*dt
        if e.y>H+20 or e.distance_to(ship)<42:
            enemies.remove(e); damage(); continue
        hit=next((s for s in shots if abs(s[0].x-e.x)<20+s[1] and abs(s[0].y-e.y)<20+s[1]),None)
        if hit:
            shots.remove(hit); enemies.remove(e); score+=10
    while score>=next_power:
        orbs.append([pygame.Vector2(random.randrange(60,W-60),90),random.choices(range(7),[30,25,20,1,12,8,4])[0]])
        next_power+=350
    for o in orbs[:]:
        o[0].y+=85*dt
        if o[0].distance_to(ship)<40:
            powers[o[1]]=30 if o[1]==3 else 60; orbs.remove(o)
        elif o[0].y>H: orbs.remove(o)
    if not boss and score>=next_boss:
        level=next_boss//2000
        boss={"level":level,"hp":40+12*level,"max":40+12*level,"age":0,"time":0,"pattern":0,"pos":pygame.Vector2(500,125)}
        next_boss+=2000; enemies.clear(); spawn=0
    if boss:
        boss["age"]+=dt; boss["time"]+=dt
        p=boss["pos"]; p.x=500+330*math.sin(boss["age"]*.9)
        if boss["time"]>=max(.85,1.7-boss["level"]*.08):
            boss["time"]=0
            a=math.atan2(ship.y-p.y,ship.x-p.x)
            angles=[[a],[math.pi/2-.42,math.pi/2,math.pi/2+.42],[a-.2,a+.2]][boss["pattern"]%3]
            boss["pattern"]+=1
            for a in angles: hazards.append([p.copy(),pygame.Vector2(math.cos(a),math.sin(a))*180])
        for s in shots[:]:
            if abs(s[0].x-p.x)<80 and abs(s[0].y-p.y)<35:
                shots.remove(s); boss["hp"]-=2 if 6 in powers else 1
                if boss["hp"]<=0:
                    boss=None; hazards.clear(); stage+=1; score+=100; reward(); break
    for h in hazards[:]:
        h[0]+=h[1]*dt
        if h[0].distance_to(ship)<29: hazards.remove(h); damage()
        elif not (-30<h[0].x<W+30 and -30<h[0].y<H+30): hazards.remove(h)
    if lives<=0:
        lives=0; record=max(record,score); state="over"; touches.clear()
menu_buttons=[("Jogar",pygame.Rect(350,300,300,55)),("Controles",pygame.Rect(350,370,300,55))]
gear=pygame.Rect(10,10,65,45)
opts=[("Pausar / voltar",pygame.Rect(10,65,230,45)),("Configurar HUD",pygame.Rect(10,115,230,45)),("Tela cheia",pygame.Rect(10,165,230,45)),("Menu",pygame.Rect(10,215,230,45))]
edit_buttons=[("Joystick / setas",pygame.Rect(270,90,230,45)),("Restaurar",pygame.Rect(510,90,150,45)),("Salvar",pygame.Rect(670,90,130,45))]
over_buttons=[("Nova partida",pygame.Rect(350,340,300,55)),("Menu",pygame.Rect(350,410,300,55))]
def click(p):
    global state,options,paused,editing,mode,drag,screen
    if editing:
        for i,(_,r) in enumerate(edit_buttons):
            if r.collidepoint(p):
                if i==0: mode="setas" if mode=="joystick" else "joystick"
                elif i==1: positions[0].update(100,610); positions[1].update(900,610)
                else: editing=False; drag=None
                return True
        for i,pos in enumerate(positions):
            if p.distance_to(pos)<85: drag=i; return True
        return True
    if state=="menu":
        if menu_buttons[0][1].collidepoint(p): reset()
        elif menu_buttons[1][1].collidepoint(p): reset(); editing=True
        return True
    if state=="over":
        if over_buttons[0][1].collidepoint(p): reset()
        elif over_buttons[1][1].collidepoint(p): state="menu"
        return True
    if gear.collidepoint(p): options=not options; touches.clear(); return True
    if options:
        for i,(_,r) in enumerate(opts):
            if r.collidepoint(p):
                options=False
                if i==0: paused=not paused
                elif i==1: editing=True
                elif i==2:
                    try: pygame.display.toggle_fullscreen()
                    except pygame.error: pass
                else: state="menu"
                return True
        return True
    return False
def draw():
    scene=(score//1000)%3
    canvas.fill(["#03060e","#102b49","#40120b"][scene])
    for x,y in stars: pygame.draw.circle(canvas,["#ddddff","#d9f6ff","#ff9750"][scene],(x,y),2)
    if state=="menu":
        label("ASTEROID WAR",320,180,"#65eaa0",big); label("Recorde local: "+str(record),390,245)
        for s,r in menu_buttons: button(s,r)
        return
    for e in enemies:
        if stage==0: pygame.draw.rect(canvas,"#ff5353",(e.x-20,e.y-20,40,40))
        else: pygame.draw.polygon(canvas,"#ff5353",poly(e,22,3+(stage-1)%6))
    pygame.draw.polygon(canvas,"#65eaa0",[(ship.x,ship.y-25),(ship.x-24,ship.y+24),(ship.x,ship.y+13),(ship.x+24,ship.y+24)])
    if 4 in powers: pygame.draw.circle(canvas,colors[4],ship,34,2)
    for p,r,_ in shots: pygame.draw.circle(canvas,"#ffe24c",p,r)
    for p,t in orbs:
        if t==3:
            for i in range(8):
                a=i*math.tau/8+pygame.time.get_ticks()*.004
                pygame.draw.circle(canvas,"#ff5318",p+pygame.Vector2(math.cos(a),math.sin(a))*19,7)
        pygame.draw.circle(canvas,colors[t],p,16)
    if boss:
        p=boss["pos"]
        pts=poly((0,0),80,boss["level"]+2,boss["age"])
        pygame.draw.polygon(canvas,"#a86bff",[(p.x+x,p.y+y*.43) for x,y in pts])
        pygame.draw.rect(canvas,"#ff4545",(p.x-80,p.y-50,160,7))
        pygame.draw.rect(canvas,"#65eaa0",(p.x-80,p.y-50,160*boss["hp"]/boss["max"],7))
    for p,_ in hazards: pygame.draw.circle(canvas,"#ff9c42",p,9)
    button("OP",gear)
    label(f"PONTOS {score:06d}",100,12,"#65eaa0")
    label(f"VIDAS {lives}   FASE {stage+1:02d}",400,12)
    label(["ESPAÇO","NEVE","INFERNO"][scene],800,12)
    for i,(p,t) in enumerate(powers.items()): label(f"{names[p]} {math.ceil(t)}s",80+(i%4)*230,45+(i//4)*24,colors[p])
    if notice_time: label(notice,330,155,"#ffe24c")
    p=positions[0]
    if mode=="joystick":
        pygame.draw.circle(canvas,"#203b54",p,52); pygame.draw.circle(canvas,"#65eaa0",p,17)
    else:
        for dx,dy,s in [(0,-35,"^"),(-35,0,"<"),(35,0,">"),(0,35,"v")]: button(s,pygame.Rect(p.x+dx-17,p.y+dy-17,34,34))
    p=positions[1]; button("ATIRAR",pygame.Rect(p.x-55,p.y-30,110,60))
    if options:
        for s,r in opts: button(s,r)
    if editing:
        label("Arraste os controles",350,145)
        for s,r in edit_buttons: button(s,r)
    if paused: label("PAUSADO",420,300,"white",big)
    if state=="over":
        pygame.draw.rect(canvas,"#080e19",(300,220,400,260),border_radius=15)
        label("SE FODEU",385,240,"#ff5353",big); label(f"Pontuação: {score}",410,300)
        for s,r in over_buttons: button(s,r)
def coords(x,y):
    sw,sh=screen.get_size()
    return pygame.Vector2(x*W/sw,y*H/sh)
async def main():
    global drag
    while True:
        dt=min(clock.tick(60)/1000,.05)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: return
            if e.type in (pygame.FINGERDOWN,pygame.MOUSEBUTTONDOWN):
                if e.type==pygame.MOUSEBUTTONDOWN and getattr(e,"touch",False): continue
                k=e.finger_id if e.type==pygame.FINGERDOWN else -1
                p=pygame.Vector2(e.x*W,e.y*H) if e.type==pygame.FINGERDOWN else coords(*e.pos)
                if not click(p): touches[k]=p
            elif e.type in (pygame.FINGERMOTION,pygame.MOUSEMOTION):
                if e.type==pygame.MOUSEMOTION and getattr(e,"touch",False): continue
                k=e.finger_id if e.type==pygame.FINGERMOTION else -1
                p=pygame.Vector2(e.x*W,e.y*H) if e.type==pygame.FINGERMOTION else coords(*e.pos)
                if editing and drag is not None: positions[drag].update(max(60,min(W-60,p.x)),max(180,min(H-60,p.y)))
                elif k in touches: touches[k]=p
            elif e.type in (pygame.FINGERUP,pygame.MOUSEBUTTONUP):
                if e.type==pygame.MOUSEBUTTONUP and getattr(e,"touch",False): continue
                touches.pop(e.finger_id if e.type==pygame.FINGERUP else -1,None); drag=None
        if state=="play" and not (paused or editing or options): update(dt)
        draw()
        screen.blit(pygame.transform.smoothscale(canvas,screen.get_size()),(0,0))
        pygame.display.flip()
        await asyncio.sleep(0)
asyncio.run(main())
