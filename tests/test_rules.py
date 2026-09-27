from app.cobol_bridge import split_603020, balance
def test_split():
 r=split_603020(3000); assert r['necessidades']==1800 and r['desejos']==900 and r['investimentos']==600
def test_balance(): assert balance(1000.15,200.10)==800.05
def test_zero(): assert split_603020(0)['necessidades']==0
