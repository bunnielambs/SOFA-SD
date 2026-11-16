"""SOFA SD: prepara os dados reais (1a vez), treina os modelos e abre o aplicativo.  Uso: python run.py"""
import sys, threading, webbrowser
from sofasd import db
from sofasd.config import MODEL_PATH

def setup():
    from sofasd.sources import historical
    from sofasd.train import train, STATE_PATH
    db.init()
    if not MODEL_PATH.exists() or not STATE_PATH.exists() or "--retreinar" in sys.argv:
        print("[1/3] Baixando a base histórica real (cerca de 45 MB, só na primeira vez)...")
        print("      partidas carregadas:", historical.load_bulk())
        print("[2/3] Atualizando a temporada atual no football-data.co.uk...")
        for lg, r in historical.refresh_couk().items():
            print("      ", lg, "ok até " + str(r.get("max_date")) if r.get("ok") else "FALHOU: " + str(r.get("error")))
        print("[3/3] Treinando os modelos com partidas reais (2 a 5 minutos)...")
        m = train(log=print)
        print("      teste fora da amostra: log loss 1X2 = %.4f (casas de aposta: %.4f)" % (
            m["r1x2"]["logloss_modelo"], m["r1x2"]["logloss_casas_de_aposta"]))

if __name__ == "__main__":
    setup()
    import uvicorn
    port = 8000
    print(f"\nSOFA SD rodando em http://127.0.0.1:{port}  (Ctrl+C para parar)")
    if "--sem-navegador" not in sys.argv:
        threading.Timer(2.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run("sofasd.server:app", host="127.0.0.1", port=port, log_level="warning")
