"""Trava de segurança do repositório: falha se algo puder fazer o GitHub desativar o repositório de novo.

O repositório antigo do site (Meruvash/Golden-Geek) foi desativado em 24/11/2026: robôs em GitHub Actions rodando em
laço quase 24 h por dia, disparando o próprio workflow e fazendo um commit por ciclo (cerca de 700 por semana).
Regras que este script garante:
  1. nenhum workflow de GitHub Actions (.github/workflows);
  2. nenhum código que rode sozinho faz commit, push, pull, fetch ou clone, nem chama a API do GitHub;
  3. nenhum timer do servidor chama git (código novo só com servidor/atualizar.sh, rodado à mão);
  4. nenhum segredo no repositório (.env fora do git).

Uso: python3 checar_seguranca.py   (sai com erro e lista os problemas)
"""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
MANUAL = {"servidor/atualizar.sh", "servidor/instalar.sh", "checar_seguranca.py", "LEIAME.md"}  # rodados à mão
GIT_REDE = re.compile(r"""(?x)
    \bgit\b[^\n]{0,40}\b(push|commit|pull|fetch|clone|remote\s+add)\b   # git que escreve ou fala com o GitHub
  | ["']git["']\s*,\s*["'](push|commit|pull|fetch|clone)["']           # subprocess.run(["git", "push", ...])
  | api\.github\.com | raw\.githubusercontent\.com | GITHUB_TOKEN | workflow_dispatch""")
SEGREDO = re.compile(r"(?m)^(?!#)\s*[A-Z_]*(TOKEN|SECRET|SENHA|KEY|HASH|SESSAO)[A-Z_]*\s*=\s*[A-Za-z0-9_\-:]{16,}")


def arquivos():
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ, capture_output=True,
                           text=True, check=True)
        return [RAIZ / f for f in r.stdout.splitlines()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in RAIZ.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts]


def problemas():
    erros = []
    if (RAIZ / ".github" / "workflows").exists() and any((RAIZ / ".github" / "workflows").iterdir()):
        erros.append(".github/workflows existe: nada de GitHub Actions neste repositório")
    for p in arquivos():
        rel = p.relative_to(RAIZ).as_posix()
        if not p.is_file() or p.suffix not in (".py", ".sh", ".service", ".timer", ".js", ".yml", ".yaml", ".env", ""):
            continue
        if p.name == ".env" or p.suffix == ".env":
            erros.append(f"{rel}: arquivo de chaves no repositório")
            continue
        texto = p.read_text(encoding="utf-8", errors="ignore")
        if rel not in MANUAL:
            for n, linha in enumerate(texto.splitlines(), 1):
                if GIT_REDE.search(linha) and not linha.lstrip().startswith("#"):
                    erros.append(f"{rel}:{n}: acesso automático ao git/GitHub: {linha.strip()[:100]}")
        m = SEGREDO.search(texto)
        if m:
            erros.append(f"{rel}: parece ter uma chave escrita no arquivo ({m.group(0)[:30]}...)")
    return erros


if __name__ == "__main__":
    e = problemas()
    print("\n".join(e) if e else "ok: nenhum workflow, nenhum git automático, nenhum segredo")
    sys.exit(1 if e else 0)
