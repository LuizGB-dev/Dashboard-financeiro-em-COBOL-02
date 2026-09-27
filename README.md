# COBOL Finance

Dashboard financeiro pessoal para demonstrar modernização de legados: navegador → FastAPI → ponte COBOL → regras financeiras. O backend mantém autenticação JWT, isolamento por `user_id`, hash bcrypt e validação Pydantic. SQLite é a alternativa local; `DATABASE_URL` permite PostgreSQL em produção.

## Executar

```powershell
Copy-Item .env.example .env
py -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra `http://localhost:8000/static/`. Também é possível: `docker compose up --build`.

## COBOL de verdade

`cobol/finance_rules.cob` calcula a divisão 60/30/20. Com GnuCOBOL instalado, compile-o a partir da raiz:

```powershell
# No PowerShell, se o GnuCOBOL for do MSYS2:
$env:COB_CONFIG_DIR='D:\\msys2\\ucrt64\\share\\gnucobol\\config'
cobc -x -o finance_rules.exe cobol/finance_rules.cob
```

O módulo `app/cobol_bridge.py` executa o binário via subprocess e interpreta a saída. Sem compilador, há um fallback Python explícito para o app continuar executável; o dashboard informa o motor usado. A IA é uma camada separada em modo `mock`, recebe apenas agregados e nunca senhas/tokens.

## API e testes

## Recuperação de senha por e-mail

Configure `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM` no `.env`. O código possui seis dígitos, é de uso único e expira após 15 minutos. Sem SMTP configurado, o modo de desenvolvimento registra o código apenas no terminal do servidor, nunca na resposta da API.

Rotas: cadastro/login, salário, receitas, despesas, dashboard, histórico e insights. CRUD de lançamentos sempre filtra pelo usuário autenticado.

```powershell
pytest
```

Melhorias futuras: PostgreSQL, refresh tokens, metas com CRUD e provedor LLM configurável.

## Por que COBOL?

Muitas regras financeiras críticas vivem em legados COBOL. Este projeto mostra uma migração incremental: a experiência, a API e dados se modernizam, enquanto regras de cálculo podem continuar auditáveis e executadas por COBOL.
