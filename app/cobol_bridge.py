"""Integra regras COBOL compiladas; fallback Python preserva a execução em máquinas sem GnuCOBOL."""
from decimal import Decimal, ROUND_HALF_UP
import shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "cobol" / ("finance_rules.exe" if __import__('os').name == 'nt' else "finance_rules")
if not EXE.exists():
    EXE = ROOT / ("finance_rules.exe" if __import__('os').name == 'nt' else "finance_rules")

def _round(v): return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def split_603020(income: float) -> dict:
    """Regra canônica: chama o executável GnuCOBOL quando presente."""
    if EXE.exists():
        try:
            raw = subprocess.check_output([str(EXE), "SPLIT", str(income)], text=True, timeout=3).strip()
            n, w, s = map(float, raw.split(";"))
            return {"necessidades": n, "desejos": w, "investimentos": s, "engine": "COBOL"}
        except (subprocess.SubprocessError, ValueError): pass
    value = Decimal(str(income))
    return {"necessidades": float(_round(value * Decimal('.60'))), "desejos": float(_round(value * Decimal('.30'))), "investimentos": float(_round(value * Decimal('.20'))), "engine": "Python fallback (compile COBOL para ativar)"}

def balance(revenues: float, expenses: float) -> float:
    return float(_round(Decimal(str(revenues)) - Decimal(str(expenses))))
