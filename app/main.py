from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timedelta, date
import jwt, os, base64, hashlib, hmac, secrets, smtplib, logging
from email.message import EmailMessage
from pathlib import Path
from .cobol_bridge import split_603020, balance

DB_URL=os.getenv('DATABASE_URL','sqlite:///./finance.db'); SECRET=os.getenv('SECRET_KEY','dev-only-change-me')
engine=create_engine(DB_URL, connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine); Base=declarative_base(); security=HTTPBearer(); logger=logging.getLogger('cobol_finance')
def hash_password(password: str) -> str:
 salt = os.urandom(16)
 digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
 return base64.b64encode(salt + digest).decode()
def verify_password(password: str, encoded: str) -> bool:
 raw = base64.b64decode(encoded.encode()); salt, digest = raw[:16], raw[16:]
 candidate = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
 return hmac.compare_digest(candidate, digest)
class User(Base):
 __tablename__='users'; id=Column(Integer,primary_key=True); name=Column(String); email=Column(String,unique=True,index=True); password_hash=Column(String); salary=Column(Float,default=0); created_at=Column(DateTime,default=datetime.utcnow)
class Transaction(Base):
 __tablename__='transactions'; id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('users.id'),index=True); kind=Column(String); description=Column(String); amount=Column(Float); category=Column(String); spent_type=Column(String,default='necessidades'); date=Column(String); created_at=Column(DateTime,default=datetime.utcnow)
class Goal(Base):
 __tablename__='financial_goals'; id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('users.id')); description=Column(String); target_amount=Column(Float); current_amount=Column(Float,default=0); deadline=Column(String)
class PasswordReset(Base):
 __tablename__='password_resets'; id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('users.id'),index=True); code_hash=Column(String); expires_at=Column(DateTime); used_at=Column(DateTime,nullable=True); created_at=Column(DateTime,default=datetime.utcnow)
class Reminder(Base):
 __tablename__='reminders'; id=Column(Integer,primary_key=True); user_id=Column(Integer,ForeignKey('users.id'),index=True); title=Column(String); due_date=Column(String,index=True); reminder_type=Column(String); amount=Column(Float,nullable=True); created_at=Column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
class Register(BaseModel): name:str; email:EmailStr; password:str=Field(min_length=6); confirmation:str
class Login(BaseModel): email:EmailStr; password:str
class ResetRequest(BaseModel): email:EmailStr
class ResetConfirm(BaseModel): email:EmailStr; code:str=Field(min_length=6,max_length=6); password:str=Field(min_length=6); confirmation:str
class ReminderIn(BaseModel): title:str=Field(min_length=2,max_length=100); due_date:str; reminder_type:str='Conta'; amount:float|None=Field(default=None,ge=0)
class Tx(BaseModel): description:str; amount:float=Field(gt=0); category:str; date:str=date.today().isoformat(); spent_type:str='necessidades'
class Salary(BaseModel): salary:float=Field(ge=0)
def db():
 s=SessionLocal()
 try: yield s
 finally: s.close()
def current(c:HTTPAuthorizationCredentials=Depends(security), s:Session=Depends(db)):
 try: data=jwt.decode(c.credentials,SECRET,algorithms=['HS256']); u=s.get(User,data['sub'])
 except jwt.PyJWTError: u=None
 if not u: raise HTTPException(401,'Sessão inválida')
 return u
def token(u): return jwt.encode({'sub':str(u.id),'exp':datetime.utcnow()+timedelta(hours=8)},SECRET,algorithm='HS256')
def send_reset_email(recipient, code):
 host=os.getenv('SMTP_HOST')
 if not host:
  logger.warning('MODO DESENVOLVIMENTO — código de redefinição para %s: %s',recipient,code); return
 msg=EmailMessage(); msg['Subject']='Código de redefinição — COBOL Finance'; msg['From']=os.getenv('SMTP_FROM','no-reply@cobol-finance.local'); msg['To']=recipient
 msg.set_content(f'Seu código para redefinir a senha é: {code}\n\nEle expira em 15 minutos.')
 with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=10) as smtp:
  if os.getenv('SMTP_TLS','true').lower()=='true': smtp.starttls()
  if os.getenv('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.environ.get('SMTP_PASSWORD',''))
  smtp.send_message(msg)
app = FastAPI(title='COBOL Finance')
app.mount('/static', StaticFiles(directory=Path(__file__).parents[1] / 'static', html=True), name='static')
@app.get('/', include_in_schema=False)
def home(): return RedirectResponse('/static/')
@app.post('/api/auth/register')
def register(x:Register,s:Session=Depends(db)):
 if x.password!=x.confirmation: raise HTTPException(400,'Senhas não coincidem')
 if s.query(User).filter_by(email=x.email).first(): raise HTTPException(409,'E-mail já cadastrado')
 u=User(name=x.name,email=x.email,password_hash=hash_password(x.password));s.add(u);s.commit();s.refresh(u);return {'token':token(u),'name':u.name}
@app.post('/api/auth/login')
def login(x:Login,s:Session=Depends(db)):
 u=s.query(User).filter_by(email=x.email).first()
 if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,'Credenciais inválidas')
 return {'token':token(u),'name':u.name}
@app.post('/api/auth/password-reset/request')
def request_password_reset(x:ResetRequest,s:Session=Depends(db)):
 u=s.query(User).filter_by(email=x.email).first()
 if u:
  s.query(PasswordReset).filter_by(user_id=u.id,used_at=None).delete()
  code=f'{secrets.randbelow(1_000_000):06d}'
  s.add(PasswordReset(user_id=u.id,code_hash=hash_password(code),expires_at=datetime.utcnow()+timedelta(minutes=15))); s.commit()
  try: send_reset_email(u.email,code)
  except Exception: logger.exception('Falha ao enviar e-mail de redefinição')
 return {'message':'Se o e-mail estiver cadastrado, você receberá um código em instantes.'}
@app.post('/api/auth/password-reset/confirm')
def confirm_password_reset(x:ResetConfirm,s:Session=Depends(db)):
 if x.password!=x.confirmation: raise HTTPException(400,'Senhas não coincidem')
 u=s.query(User).filter_by(email=x.email).first()
 reset=s.query(PasswordReset).filter_by(user_id=u.id if u else -1,used_at=None).order_by(PasswordReset.created_at.desc()).first()
 if not u or not reset or reset.expires_at<datetime.utcnow() or not verify_password(x.code,reset.code_hash): raise HTTPException(400,'Código inválido ou expirado')
 u.password_hash=hash_password(x.password); reset.used_at=datetime.utcnow(); s.commit(); return {'message':'Senha redefinida. Faça login com a nova senha.'}
@app.get('/api/reminders')
def list_reminders(u:User=Depends(current),s:Session=Depends(db)):
 rows=s.query(Reminder).filter_by(user_id=u.id).order_by(Reminder.due_date).all()
 return [{'id':r.id,'title':r.title,'due_date':r.due_date,'reminder_type':r.reminder_type,'amount':r.amount} for r in rows]
@app.post('/api/reminders')
def add_reminder(x:ReminderIn,u:User=Depends(current),s:Session=Depends(db)):
 try: datetime.strptime(x.due_date,'%Y-%m-%d')
 except ValueError: raise HTTPException(400,'Data inválida')
 r=Reminder(user_id=u.id,**x.model_dump());s.add(r);s.commit();s.refresh(r);return {'id':r.id}
@app.delete('/api/reminders/{rid}')
def delete_reminder(rid:int,u:User=Depends(current),s:Session=Depends(db)):
 r=s.query(Reminder).filter_by(id=rid,user_id=u.id).first()
 if not r: raise HTTPException(404)
 s.delete(r);s.commit();return {'ok':True}
@app.get('/api/dashboard')
def dashboard(u:User=Depends(current),s:Session=Depends(db)):
 rows=s.query(Transaction).filter_by(user_id=u.id).all(); rev=sum(x.amount for x in rows if x.kind=='revenue'); exp=sum(x.amount for x in rows if x.kind=='expense')
 actual={k:sum(x.amount for x in rows if x.kind=='expense' and x.spent_type==k) for k in ['necessidades','desejos','investimentos']}; plan=split_603020(u.salary)
 return {'name':u.name,'salary':u.salary,'revenues':rev,'expenses':exp,'balance':balance(rev,exp),'used_pct':round(exp/u.salary*100,1) if u.salary else 0,'plan':plan,'actual':actual,'transactions':[{'id':x.id,'kind':x.kind,'description':x.description,'amount':x.amount,'category':x.category,'date':x.date,'spent_type':x.spent_type} for x in rows]}
@app.put('/api/salary')
def set_salary(x:Salary,u:User=Depends(current),s:Session=Depends(db)):
 u.salary=x.salary;s.commit();return split_603020(x.salary)
@app.post('/api/{kind}')
def add(kind:str,x:Tx,u:User=Depends(current),s:Session=Depends(db)):
 if kind not in ('revenue','expense'): raise HTTPException(404)
 t=Transaction(user_id=u.id,kind=kind,**x.model_dump());s.add(t);s.commit();s.refresh(t);return {'id':t.id}
@app.put('/api/transactions/{tid}')
def edit(tid:int,x:Tx,u:User=Depends(current),s:Session=Depends(db)):
 t=s.query(Transaction).filter_by(id=tid,user_id=u.id).first()
 if not t: raise HTTPException(404)
 for k,v in x.model_dump().items(): setattr(t,k,v)
 s.commit();return {'ok':True}
@app.delete('/api/transactions/{tid}')
def delete(tid:int,u:User=Depends(current),s:Session=Depends(db)):
 t=s.query(Transaction).filter_by(id=tid,user_id=u.id).first()
 if not t: raise HTTPException(404)
 s.delete(t);s.commit();return {'ok':True}
@app.get('/api/insights')
def insights(u:User=Depends(current),s:Session=Depends(db)):
 d=dashboard(u,s); p=d['plan']; a=d['actual']; out=[]
 for k in a:
  if a[k]>p[k]: out.append(f'Você ultrapassou o limite de {k}: R$ {a[k]-p[k]:.2f} acima do recomendado.')
 out.append(f'Seu saldo atual é R$ {d["balance"]:.2f}.')
 if d['salary']: out.append(f'Você usou {d["used_pct"]}% da sua renda em despesas.')
 return {'mode':'mock','insights':out,'note':'Provedor IA modular: mock seguro sem enviar credenciais.'}
