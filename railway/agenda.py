"""Agenda dos robôs no Railway: um processo só, sempre ligado, que chama servidor/rodar.sh no horário de cada robô.

Por que um processo só (e não um serviço de cron do Railway por robô): os robôs normal, ml e educado gravam nos mesmos
arquivos (conteudo/black/ofertas.json etc.), e no Railway um volume só pode ficar ligado a um serviço. Então os
dados ficam num volume (montado em /dados) e esta agenda faz o papel dos timers do systemd do servidor.

Na primeira vez (volume vazio), abre a semente (railway/semente-*.tgz: os dados do Radar de 24/11/2026, histórico de
preços incluído), para nada recomeçar do zero.

Horários em UTC, os mesmos do servidor/systemd/. Nada aqui fala com o GitHub.
"""
import datetime as dt
import json
import os
import re
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
    "calibragem": ([10], [5]),  # guarda os posts de curadoria todo dia; retreina os pesos da nota a cada 7 dias
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
    # sons do feed (28/11/2026): sempre a versão do repositório, para um som trocado chegar ao site
    for som in (RADAR / "img-fixas").glob("som-*.mp3"):
        destino = DADOS / "img" / "black" / som.name
        if not destino.exists() or destino.read_bytes() != som.read_bytes():
            destino.write_bytes(som.read_bytes())
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


# Vigia (25/11/2026): avisa no Telegram privado quando um robô para de terminar bem ou a página para de mudar.
# Prazo = tempo sem nenhuma rodada que termine com código 0. O educado roda a cada 3 h e pode levar 4 h.
PRAZO_H = {"normal": 2, "ml": 2, "educado": 8, "alertas": 1, "telegram": 1}
PAGINA_H = 3            # black/index.html sem mudar por mais que isso
FALHAS_SEGUIDAS = 2     # rodadas seguidas com erro
REPETIR_H = 6           # o mesmo problema só é avisado de novo depois disso
VIGIA = DADOS / "vigia.json"


def _ler_vigia():
    try:
        return json.loads(VIGIA.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _gravar_vigia(v):
    try:
        VIGIA.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def avisar_dono(texto):
    """Manda o aviso para o chat privado do dono (TELEGRAM_CHAT_AVISOS, ou o chat dos textos do WhatsApp)."""
    log(texto.replace("\n", " | "))
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_AVISOS") or os.environ.get("TELEGRAM_CHAT_WHATSAPP")
    if not token or not chat:
        return
    try:
        sys.path.insert(0, str(APP / "telegram"))
        import bot
        r = bot.Telegram(token).texto(bot.canal(chat), texto)
        if not r.get("ok"):
            log(f"vigia: Telegram recusou o aviso ({r.get('description')})")
    except Exception as ex:  # aviso que falha não derruba a agenda
        log(f"vigia: não consegui avisar no Telegram ({ex})")


def problemas(estado, ligados, agora):
    """Lista de (chave, texto) dos problemas de agora."""
    res = []
    for robo, horas in PRAZO_H.items():
        if robo not in ligados:
            continue
        ok = estado["ultimo_ok"].get(robo) or estado["inicio"]
        parado = (agora - dt.datetime.fromisoformat(ok)).total_seconds() / 3600
        if parado > horas:
            res.append((f"parado:{robo}", f"o robô {robo} não termina uma rodada sem erro há {parado:.0f} h (o normal é até {horas} h)"))
        if estado["falhas"].get(robo, 0) >= FALHAS_SEGUIDAS:
            res.append((f"falha:{robo}", f"o robô {robo} terminou com erro {estado['falhas'][robo]} vezes seguidas"))
    pag = RADAR / "black" / "index.html"
    desde_inicio = (agora - dt.datetime.fromisoformat(estado["inicio"])).total_seconds() / 3600
    if pag.exists() and desde_inicio > PAGINA_H:
        idade = (agora.timestamp() - pag.stat().st_mtime) / 3600
        if idade > PAGINA_H:
            res.append(("pagina", f"a página /black/ não é refeita há {idade:.0f} h"))
    return res


def vigiar(estado, ligados, agora):
    v = _ler_vigia()
    avisados = v.setdefault("avisados", {})
    atuais = dict(problemas(estado, ligados, agora))
    for chave, texto in atuais.items():
        ultimo = avisados.get(chave)
        if not ultimo or (agora - dt.datetime.fromisoformat(ultimo)).total_seconds() > REPETIR_H * 3600:
            avisar_dono(f"⚠️ Radar Black: {texto}.\nVeja os logs no Railway (Deployments → View logs).")
            avisados[chave] = agora.isoformat()
    # logo depois de ligar (deploy novo) ainda não dá para saber se um problema antigo passou: não fecha nada
    if (agora - dt.datetime.fromisoformat(estado["inicio"])).total_seconds() < max(PRAZO_H.values()) * 3600 / 4:
        _gravar_vigia(v)
        return
    for chave in [c for c in avisados if c not in atuais]:
        avisar_dono(f"✅ Radar Black: resolvido ({chave.split(':')[-1]}).")
        del avisados[chave]
    _gravar_vigia(v)


# Tempo máximo de uma rodada (27/11/2026: a página parou às 13h03 sem aviso visível de fora). Passou disso, a agenda
# encerra o robô para ele não segurar a vez dos outros; o rodar.sh já tem timeouts, isto é a rede de segurança.
MAX_MIN = {"normal": 45, "ml": 45, "educado": 270, "auditoria": 70}
MAX_PADRAO = 30
LOGS = DADOS / "logs"
URL = re.compile(r"https?://\S+")


def saude(estado, rodando, comeco, agora):
    """Grava radar/black/saude/estado.json e envia ao R2: fica em eliteboardgamers.com.br/black/saude/estado.json,
    para dar para ver de fora (sem entrar no Railway) se cada robô roda, quando terminou bem e as últimas linhas do log
    (sem links)."""
    robos = {}
    for robo in AGENDA:
        try:
            cauda = [URL.sub("<link>", l)[:240] for l in (LOGS / f"{robo}.log").read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()][-12:]
        except OSError:
            cauda = []
        robos[robo] = {"rodando_desde": comeco.get(robo) if robo in rodando else None, "ultimo_ok": estado["ultimo_ok"].get(robo),
                       "falhas_seguidas": estado["falhas"].get(robo, 0), "log": cauda}
    pag = RADAR / "black" / "index.html"
    dados = {"agora": agora.isoformat(), "agenda_desde": estado["inicio"],
             "pagina_refeita": dt.datetime.fromtimestamp(pag.stat().st_mtime, dt.timezone.utc).isoformat() if pag.exists() else None,
             "robos": robos}
    destino = RADAR / "black" / "saude"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "estado.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        subprocess.run([sys.executable, str(APP / "servidor" / "publicar_r2.py"), "black/saude"], timeout=120,
                       capture_output=True)
    except Exception as ex:  # a saúde nunca derruba a agenda
        log(f"saúde: não consegui gravar ou enviar ({ex})")


def iniciar(robo):
    """Roda o robô guardando a saída em /dados/logs/<robo>.log (para a saúde) e mostrando no log do Railway."""
    LOGS.mkdir(parents=True, exist_ok=True)
    cmd = f'bash "{APP / "servidor" / "rodar.sh"}" {robo} 2>&1 | tee "{LOGS / (robo + ".log")}"'
    return subprocess.Popen(["bash", "-o", "pipefail", "-c", cmd], start_new_session=True)


def encerrar(proc):
    import signal
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        time.sleep(10)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def na_hora(robo, agora):
    minutos, horas = AGENDA[robo]
    return agora.minute in minutos and (horas is None or agora.hour in horas)


def main():
    preparar()
    ligados = [r for r in AGENDA if r not in DESLIGADOS]
    log(f"agenda no ar; robôs ligados: {', '.join(ligados)}" + (f"; desligados: {', '.join(sorted(DESLIGADOS))}" if DESLIGADOS else ""))
    rodando, comeco = {}, {}
    ultimo = None
    inicio = dt.datetime.now(dt.timezone.utc).isoformat()
    estado = {"inicio": inicio, "ultimo_ok": {}, "falhas": {}}
    if "--agora" in sys.argv:  # teste: roda um robô na hora e sai (ex.: python3 railway/agenda.py --agora telegram)
        robo = sys.argv[sys.argv.index("--agora") + 1]
        sys.exit(subprocess.call(["bash", str(APP / "servidor" / "rodar.sh"), robo]))
    while True:
        agora = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
        for robo, proc in list(rodando.items()):
            if proc.poll() is not None:
                log(f"robô {robo} terminou (código {proc.returncode})")
                if proc.returncode == 0:
                    estado["ultimo_ok"][robo] = dt.datetime.now(dt.timezone.utc).isoformat()
                    estado["falhas"][robo] = 0
                else:
                    estado["falhas"][robo] = estado["falhas"].get(robo, 0) + 1
                del rodando[robo]
        for robo, proc in list(rodando.items()):
            minutos = (time.time() - comeco[robo + "_t"]) / 60
            if minutos > MAX_MIN.get(robo, MAX_PADRAO):
                log(f"robô {robo} passou de {MAX_MIN.get(robo, MAX_PADRAO)} min; encerrando para não travar os outros")
                encerrar(proc)
        if agora != ultimo:
            ultimo = agora
            if agora.minute % 5 == 0:
                vigiar(estado, ligados, agora)
                saude(estado, rodando, comeco, agora)
            for robo in ligados:
                if na_hora(robo, agora):
                    if robo in rodando:
                        log(f"robô {robo} ainda está rodando; esta rodada fica para a próxima")
                        continue
                    log(f"começando o robô {robo}")
                    rodando[robo] = iniciar(robo)
                    comeco[robo] = agora.isoformat()
                    comeco[robo + "_t"] = time.time()
        time.sleep(15)


if __name__ == "__main__":
    main()
