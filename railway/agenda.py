"""Agenda dos robôs no Railway: um processo só, sempre ligado, que chama servidor/rodar.sh no horário de cada robô.

Por que um processo só (e não um serviço de cron do Railway por robô): os robôs normal, ml e educado gravam nos mesmos
arquivos (conteudo/black/ofertas.json etc.), e no Railway um volume só pode ficar ligado a um serviço. Então os
dados ficam num volume (montado em /dados) e esta agenda faz o papel dos timers do systemd do servidor.

Na primeira vez (volume vazio), abre a semente (railway/semente-*.tgz: os dados do Radar de 24/11/2026, histórico de
preços incluído), para nada recomeçar do zero.

Horários em UTC, os mesmos do servidor/systemd/. Nada aqui fala com o GitHub.
"""
import datetime as dt
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
DADOS = Path(os.environ.get("DADOS", "/dados"))
RADAR = APP / "radar"

# robô: (minutos da hora em que roda, horas do dia em que roda ou None para todas)
AGENDA = {
    "normal": ([5, 35], None),
    "ml": ([20, 50], None),
    "educado": ([45], list(range(0, 24, 3))),
    "alertas": ([0, 15, 30, 45], None),
    "telegram": ([3, 18, 33, 48], None),
    "notificacoes": ([7, 22, 37, 52], None),
    "auditoria": ([41], list(range(0, 24, 6))),
}
# robôs desligados por variável (ex.: DESLIGAR=educado,auditoria) sem mexer no código
DESLIGADOS = {r.strip() for r in os.environ.get("DESLIGAR", "").split(",") if r.strip()}


def log(msg):
    print(f"[agenda {dt.datetime.now(dt.timezone.utc):%d/%m %H:%M}Z] {msg}", flush=True)


def preparar():
    """Liga as pastas de dados do radar ao volume e, se o volume estiver vazio, abre a semente."""
    DADOS.mkdir(parents=True, exist_ok=True)
    if not (DADOS / "conteudo" / "black").exists():
        sementes = sorted((APP / "railway").glob("semente-*.tgz"))
        if sementes:
            log(f"volume vazio: abrindo a semente {sementes[-1].name}")
            with tarfile.open(sementes[-1]) as t:
                t.extractall(DADOS, filter="data")
    for pasta in ("conteudo/black", "img/black", "black", "copia"):
        (DADOS / pasta).mkdir(parents=True, exist_ok=True)
    for nome in ("img/black/qr-alertas.svg",):
        destino = DADOS / nome
        if not destino.exists():
            destino.write_bytes((RADAR / "img-fixas" / Path(nome).name).read_bytes())
    for pasta in ("conteudo", "img", "black"):  # radar/conteudo -> /dados/conteudo etc.
        link = RADAR / pasta
        if link.is_symlink() or not link.exists():
            if link.is_symlink():
                link.unlink()
            link.symlink_to(DADOS / pasta, target_is_directory=True)
    copia = APP / "copia"
    if not copia.exists():
        copia.symlink_to(DADOS / "copia", target_is_directory=True)
    os.environ.setdefault("BOT_ESTADO", str(DADOS / "telegram_estado.json"))
    os.environ["ELITE_ROBOS"] = str(APP)


def na_hora(robo, agora):
    minutos, horas = AGENDA[robo]
    return agora.minute in minutos and (horas is None or agora.hour in horas)


def main():
    preparar()
    ligados = [r for r in AGENDA if r not in DESLIGADOS]
    log(f"agenda no ar; robôs ligados: {', '.join(ligados)}" + (f"; desligados: {', '.join(sorted(DESLIGADOS))}" if DESLIGADOS else ""))
    rodando = {}
    ultimo = None
    if "--agora" in sys.argv:  # teste: roda um robô na hora e sai (ex.: python3 railway/agenda.py --agora telegram)
        robo = sys.argv[sys.argv.index("--agora") + 1]
        sys.exit(subprocess.call(["bash", str(APP / "servidor" / "rodar.sh"), robo]))
    while True:
        agora = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
        for robo, proc in list(rodando.items()):
            if proc.poll() is not None:
                log(f"robô {robo} terminou (código {proc.returncode})")
                del rodando[robo]
        if agora != ultimo:
            ultimo = agora
            for robo in ligados:
                if na_hora(robo, agora):
                    if robo in rodando:
                        log(f"robô {robo} ainda está rodando; esta rodada fica para a próxima")
                        continue
                    log(f"começando o robô {robo}")
                    rodando[robo] = subprocess.Popen(["bash", str(APP / "servidor" / "rodar.sh"), robo])
        time.sleep(15)


if __name__ == "__main__":
    main()
