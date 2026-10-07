"""Sertifikat dizayni: «Zumrad rasmiy» (A4 gorizontal, guilloche naqsh, oltin folga, medal)."""
import math, os, io
from PIL import Image, ImageDraw, ImageFont
LEVELS=[("C","46–49,9"),("C+","50–54,9"),("B","55–59,9"),("B+","60–64,9"),("A","65–69,9"),("A+","70–75")]
_DIRS=[os.path.join(os.path.dirname(os.path.abspath(__file__)),"fonts"),"/usr/share/fonts/truetype/dejavu","/usr/share/fonts/truetype/liberation2","/usr/share/fonts/truetype/liberation"]
def _font(size,bold=False,serif=True):
    names=([("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf")] if serif else [])+[("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")]
    for d in _DIRS:
        for n in names:
            p=os.path.join(d,n)
            if os.path.exists(p): return ImageFont.truetype(p,size)
    try: return ImageFont.load_default(size)
    except TypeError: return ImageFont.load_default()
class mx: LEVELS=LEVELS
K=2; W,H=1754,1240; SW,SH=W*K,H*K
def F(sz,b=False,serif=False): return _font(int(sz*K),b,serif)
def tw(d,t,f,tr=0): return sum(d.textlength(c,font=f)+tr*K for c in t)-tr*K if tr else d.textlength(t,font=f)
def ct(d,x,y,t,f,fill,tr=0):
    if not tr:
        d.text((x*K-d.textlength(t,font=f)/2,y*K),t,font=f,fill=fill); return
    cx=x*K-tw(d,t,f,tr)/2
    for c in t: d.text((cx,y*K),c,font=f,fill=fill); cx+=d.textlength(c,font=f)+tr*K
def lt(d,x,y,t,f,fill,tr=0):
    cx=x*K
    for c in t: d.text((cx,y*K),c,font=f,fill=fill); cx+=d.textlength(c,font=f)+tr*K
def vgrad(w,h,stops):
    """Vertikal gradient: 1 pikselli ustun hisoblanib, kengligiga cho'ziladi (tez va kam xotira)."""
    col=Image.new('RGB',(1,h)); px=col.load(); c=stops[-1][1]
    for y in range(h):
        t=y/max(1,h-1)
        for i in range(len(stops)-1):
            a,ca=stops[i]; b,cb=stops[i+1]
            if a<=t<=b:
                k=(t-a)/(b-a) if b>a else 0; c=tuple(int(ca[j]*(1-k)+cb[j]*k) for j in range(3)); break
        px[0,y]=c
    return col if w==1 else col.resize((w,h))
GOLD=[(0,(150,110,40)),(0.25,(240,205,120)),(0.5,(200,155,65)),(0.75,(250,225,150)),(1,(160,115,45))]
def foil(im,mask):  # oltin folga: gradient faqat maska chegarasi (bbox) uchun quriladi
    bb=mask.getbbox()
    if not bb: return
    x0,y0,x1,y1=bb
    col=vgrad(1,im.size[1],GOLD).crop((0,y0,1,y1)).resize((x1-x0,y1-y0))
    im.paste(col,(x0,y0),mask.crop(bb))
def gold_text(im,x,y,t,f,tr=0,center=True):
    m=Image.new('L',im.size,0); md=ImageDraw.Draw(m)
    if center: ct(md,x,y,t,f,255,tr)
    else: lt(md,x,y,t,f,255,tr)
    g=vgrad(im.size[0],im.size[1],[(0,(150,110,40)),(max(0.001,(y-30)/H*0.9),(150,110,40)),(min(0.99,(y+20)/H),(245,215,130)),(min(0.999,(y+90)/H),(176,132,52)),(1,(176,132,52))]) if False else vgrad(im.size[0],im.size[1],GOLD)
    im.paste(g,(0,0),m)
def guilloche(d,cx,cy,R,r,p,col,wd=1,n=1800):
    pts=[]
    for i in range(n+1):
        t=i/n*2*math.pi*(r//math.gcd(R,r)) if False else i/n*2*math.pi*r
        x=(R-r)*math.cos(t)+p*math.cos((R-r)/r*t); y=(R-r)*math.sin(t)-p*math.sin((R-r)/r*t)
        pts.append(((cx+x)*K,(cy+y)*K))
    d.line(pts,fill=col,width=max(1,int(wd*K/2)))
def rosette(d,cx,cy,size,col,layers=3):
    for i in range(layers):
        guilloche(d,cx,cy,int(size*0.62),int(size*0.2)+i*3,int(size*0.34),col,1,2600)
def wave_border(d,x0,y0,x1,y1,col,amp=7,n=5,period=34):
    for k in range(n):
        ph=k*0.9; pts=[]
        x=x0
        while x<=x1: pts.append((x*K,(y0+amp*math.sin((x-x0)/period*2*math.pi+ph))*K)); x+=3
        d.line(pts,fill=col,width=K)
        pts=[]; x=x0
        while x<=x1: pts.append((x*K,(y1+amp*math.sin((x-x0)/period*2*math.pi+ph))*K)); x+=3
        d.line(pts,fill=col,width=K)
        pts=[]; y=y0
        while y<=y1: pts.append(((x0+amp*math.sin((y-y0)/period*2*math.pi+ph))*K,y*K)); y+=3
        d.line(pts,fill=col,width=K)
        pts=[]; y=y0
        while y<=y1: pts.append(((x1+amp*math.sin((y-y0)/period*2*math.pi+ph))*K,y*K)); y+=3
        d.line(pts,fill=col,width=K)
def seal(im,cx,cy,R,text,sub,inner,txt=(255,255,255),ribbon=None):
    d=ImageDraw.Draw(im)
    if ribbon:
        for s in (-1,1):
            d.polygon([((cx+s*18)*K,(cy+R*0.6)*K),((cx+s*(R*0.62))*K,(cy+R*1.75)*K),((cx+s*(R*0.28))*K,(cy+R*1.5)*K),((cx+s*(R*0.05))*K,(cy+R*1.8)*K),((cx-s*10)*K,(cy+R*0.6)*K)],fill=ribbon)
    m=Image.new('L',im.size,0); md=ImageDraw.Draw(m); N=44; pts=[]
    for i in range(N*2): a=math.pi*i/N; r=R if i%2==0 else R*0.93; pts.append(((cx+r*math.cos(a))*K,(cy+r*math.sin(a))*K))
    md.polygon(pts,fill=255); foil(im,m)
    d=ImageDraw.Draw(im)
    for rr,wd in ((R*0.86,2),(R*0.74,3)): d.ellipse([(cx-rr)*K,(cy-rr)*K,(cx+rr)*K,(cy+rr)*K],outline=(255,240,200),width=wd*K//2)
    d.ellipse([(cx-R*0.70)*K,(cy-R*0.70)*K,(cx+R*0.70)*K,(cy+R*0.70)*K],fill=inner)
    ct(d,cx,cy-R*0.44,text,F(R*0.78,True,True),txt)
    ct(d,cx,cy+R*0.30,sub,F(R*0.17,True),(240,215,140),tr=2)
def level_scale(im,x0,y,w,on,col_on,col_off,t_on,t_off,outline=None,h=86):
    d=ImageDraw.Draw(im); n=6; gap=10; bw=(w-gap*(n-1))/n
    for i,(nm,rng) in enumerate(mx.LEVELS):
        x=x0+i*(bw+gap); sel=nm==on
        d.rounded_rectangle([x*K,y*K,(x+bw)*K,(y+h)*K],radius=12*K,fill=col_on if sel else col_off,outline=(outline if sel else None),width=3*K)
        ct(d,x+bw/2,y+8,nm,F(34,True,True),t_on if sel else t_off); ct(d,x+bw/2,y+52,rng,F(17),t_on if sel else t_off)
D={"name":"Sardor Sayfullayev","subject":"Ona tili va adabiyot","score":68.75,"level":"A","test":"73.33 / 75","essay":"18 / 24","raw":"43 / 44","date":"03.10.2026","code":"DG-7F3A91C20B","testname":"Ona tili — 1-variant"}
def vC(kind='diag'):
    im=Image.new('RGB',(SW,SH),(248,246,238)); d=ImageDraw.Draw(im,'RGBA')
    rosette(d,W/2,H/2,560,(7,91,67,22)); rosette(d,W/2,H/2,400,(184,140,55,26),2)
    d.rectangle([0,0,SW,SH],outline=(7,70,52),width=26*K)
    wave_border(d,52,52,W-52,H-52,(7,91,67,200),amp=9,n=5,period=40)
    g=Image.new('L',im.size,0); ImageDraw.Draw(g).rectangle([96*K,96*K,(W-96)*K,(H-96)*K],outline=255,width=4*K); foil(im,g); d=ImageDraw.Draw(im,'RGBA')
    d.rectangle([108*K,108*K,(W-108)*K,(H-108)*K],outline=(7,91,67,150),width=K)
    ct(d,W/2,140,"ESSE AKADEMIYASI",F(22,True),(7,91,67),tr=8)
    ct(d,W/2,190,"DIAGNOSTIK SERTIFIKAT" if kind=="diag" else "MAXSUS SERTIFIKAT",F(78,True,True),(6,52,40))
    ct(d,W/2,292,"Milliy sertifikat imtihoni formatidagi tayyorlov natijasi" if kind=="diag" else f"{D['period_name']} eng bilimdon o‘quvchi",F(25 if kind=="diag" else 30,kind!="diag"),(85,110,100) if kind=="diag" else (150,110,40))
    g=Image.new('L',im.size,0); ImageDraw.Draw(g).line([(W/2-260)*K,345*K,(W/2+260)*K,345*K],fill=255,width=3*K); foil(im,g); d=ImageDraw.Draw(im,'RGBA')
    ct(d,W/2,375,"ushbu sertifikat egasi",F(23),(85,110,100),tr=3)
    ct(d,W/2,415,D['name'],F(92,True,True),(6,52,40))
    ct(d,W/2,545,(f"{D['subject']} fanidan diagnostik imtihonda quyidagi natijani qayd etdi" if kind=="diag" else f"{D['period_name']} reytingida yetakchi bo‘lgani uchun taqdirlanadi"),F(27),(40,70,60))
    cw=330; gap=24; x0=W/2-(3*cw+2*gap)/2
    chip=[("JAMI BALL",f"{D['score']:g} / 75"),("TEST • ESSE",f"{D['test'].split(' ')[0]} • {D['essay'].split(' ')[0]}"),("TO‘G‘RI JAVOB",D['raw'])] if kind=="diag" else [("REYTING O‘RNI",f"{D['rank']}-o‘rin"),("JAMI BALL",f"{D['pts']:g}"),("TOPSHIRIQLAR",f"{D['tests']} ta")]
    for i,(a,b) in enumerate(chip):
        x=x0+i*(cw+gap); big=i==0
        d.rounded_rectangle([x*K,625*K,(x+cw)*K,(625+118)*K],radius=14*K,fill=(7,70,52) if big else (232,241,236),outline=(184,140,55) if big else (190,212,202),width=3*K)
        ct(d,x+cw/2,642,a,F(18,True),(240,215,140) if big else (85,110,100),tr=3); ct(d,x+cw/2,680,b,F(44,True),(255,255,255) if big else (6,52,40))
    if kind=='diag': level_scale(im,x0,790,3*cw+2*gap,D['level'],(7,91,67),(232,241,236),(255,255,255),(90,115,105),outline=(184,140,55),h=84)
    d=ImageDraw.Draw(im,'RGBA')
    d.line([230*K,1000*K,560*K,1000*K],fill=(6,52,40),width=2*K); lt(d,230,1012,"Akademiya rahbari",F(20),(85,110,100))
    d.line([(W-560)*K,1000*K,(W-230)*K,1000*K],fill=(6,52,40),width=2*K); t="Imtihon markazi"; lt(d,W-230-d.textlength(t,font=F(20))/K,1012,t,F(20),(85,110,100))
    seal(im,W/2,945 if kind=="diag" else 925,86,D["level"] if kind=="diag" else str(D["rank"]),"DARAJA" if kind=="diag" else "O‘RIN",(7,70,52),ribbon=(140,24,40)); d=ImageDraw.Draw(im,'RGBA')
    ct(d,W/2,1115,(f"Sertifikat №  {D['code']}   •   {D['date']}   •   {D['testname']}" if kind=="diag" else f"Sertifikat №  {D['code']}   •   {D['date']}   •   {D['range']}"),F(20,True),(6,52,40))
    ct(d,W/2,1148,"Diagnostik natija — rasmiy davlat sertifikati emas." if kind=="diag" else "Esse Akademiyasi ichki reytingi mukofoti — rasmiy davlat hujjati emas.",F(18),(150,50,50)); return im



import threading
_RL=threading.Lock()
D={}
def render(kind,data,code):
    with _RL:  # bir vaqtda bitta sertifikat chiziladi (xotira tejash)
        return _render(kind,data,code)
def _render(kind,data,code):
    """kind: 'diag' yoki 'award'. PNG baytlarini qaytaradi."""
    global D
    esc=data.get("essay","—"); lvl=data.get("level","—")
    D={"name":str(data.get("name","Talabgor"))[:40],"subject":data.get("subject","Ona tili va adabiyot"),"score":float(data.get("score",0)),"level":lvl,
       "test":f"{float(data.get('test_score',0)):g} / 75","essay":f"{esc} / 24","raw":f"{float(data.get('raw',0)):g} / {float(data.get('max',44)):g}",
       "date":data.get("date",""),"code":code,"testname":str(data.get("title",""))[:34],"period_name":data.get("period_name",""),"rank":int(data.get("rank",1)),
       "pts":float(data.get("pts",0)),"tests":int(data.get("tests",0)),"range":data.get("range","")}
    if lvl not in dict(LEVELS): D["level"]="—"
    im=vC(kind).resize((W,H),Image.LANCZOS); buf=io.BytesIO(); im.save(buf,"PNG",optimize=True); return buf.getvalue()
