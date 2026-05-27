# Organizador de Documentos Mobile

Novo app Python mobile-first para organizar documentos financeiros por mes e dia.

## Stack

- Python
- Flet
- Supabase Auth via REST
- Supabase PostgREST via HTTP
- Supabase Storage via HTTP
- httpx

## Estrutura

- `main.py`: entrada do app desktop-dev.
- `documents_org/config`: constantes e leitura do `.env`.
- `documents_org/models`: modelos de dominio.
- `documents_org/services`: Supabase via HTTP, storage e regras de negocio.
- `tests`: testes unitarios das regras principais.

## Configuracao

1. Crie um arquivo `.env` na raiz deste projeto.
2. Use `.env.example` como base.
3. Confirme que o Supabase tem:
   - tabela `documents`;
   - tabela `links`;
   - bucket `documents`.

## Rodar no desktop

O projeto agora usa Flet, que requer Python 3.10+.
Voce pode usar a venv ja criada.

Confira as versoes instaladas:

```powershell
py -0p
```

Crie a venv com Python 3.12:

```powershell
py -3.12 -m venv .venv
```

Se a venv antiga foi criada com Python 3.14, apague a pasta `.venv` e recrie com o comando acima.

Voce nao precisa ativar a venv no PowerShell. Para evitar erro de Execution Policy, use o Python da venv diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Se quiser ativar mesmo assim, libere apenas na sessao atual do PowerShell:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\Activate.ps1
```

## Rodar testes

```powershell
pytest
```

## Observacoes

Esta primeira entrega roda no PC em janela com proporcao de celular. O empacotamento Android deve ser feito em uma etapa seguinte com `flet build apk`.
