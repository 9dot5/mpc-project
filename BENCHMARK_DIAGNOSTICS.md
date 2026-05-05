# Benchmark diagnostics — dark_auction (E2E)

Date: 2026-05-05

## Resumo

Este ficheiro sumariza o problema que ocorreu ao executar a validação E2E do programa `dark_auction.mpc`, descreve o que foi observado, analisa causas prováveis e propõe um plano de ação passo a passo com comandos executáveis para diagnóstico e resolução.

## Ambiente

- Host: Windows
- Repositório: `C:\IST_CS\mpc-project`
- Docker Compose com 3 containers: `party0`, `party1`, `party2` (nomes de container observados: `mpc_party_0`, `mpc_party_1`, `mpc_party_2`).
- Binário MPC usado: `mascot-party.x` (MP‑SPDZ)
- Scripts relevantes: `scripts/validate_end_to_end.py`, `scripts/generate_inputs.py`
- Simulador: `simulator/dark_auction_sim.py`

## Observações / Erros vistos

- `scripts/validate_end_to_end.py` inicialmente falhou com `subprocess.TimeoutExpired` aguardando a execução de `docker compose exec` (timeout 180s; foi tentado 600s e também esgotou).
- Regeneração dos inputs (`--n-orders 10`) e compilação do programa foram feitas com sucesso.
- Ao iniciar as parties em background com logs redirecionados para `/tmp/mascot_p{0,1,2}.log`, os logs iniciais mostram repetidamente:

```
Binding to socket on <container-id>:5000 failed (Address already in use), trying again in a second ...
```

- Numa execução anterior também apareceu:

```
Fatal error at dark_auction-0:360 (INPUTMIXED): cannot read integer from Inputs/Input-P0-0, problem with '' after 48
```

Esses sinais indicam problemas de I/O / ligações de socket e possivelmente instâncias anteriores a manter portas ocupadas.

## O que já foi feito

- Gereis inputs e converti para MP‑SPDZ (`Inputs/Input-P*-0`).
- Compilei `dark_auction.mpc` dentro do container (bytecode e schedule gerados).
- Tentei terminar processos antigos (`killall` / `pkill`) e reiniciar as parties em detached escrevendo logs em `/tmp`.
- Confirmei que `mascot-party.x` está a correr em cada container (processos ativos com PIDs e elevado uso CPU).

## Análise provável das causas

- Instâncias antigas de `mascot-party.x` (ou processes órfãos) ainda existiam e mantêm sockets ligados → novos processos não conseguem `bind` às mesmas portas (address in use).
- Execuções anteriores que ligaram stdout/stderr a pipes (usadas pelo validador Python) fizeram com que o processo bloqueasse e o validador ficasse preso esperando output, causando timeout.
- Um `INPUTMIXED` sugere que um ficheiro de input ficou truncado ou com linhas em branco, possivelmente causado por escrita concorrente ou cópia parcial durante conversão.
- Problemas de rede do Compose (portas internas em conflito) ou sockets em TIME_WAIT também são possíveis.

## Plano de ação (passos executáveis)

1. Inspecionar processos e sockets dentro de cada container (identificar quem escuta nas portas):

```bash
docker compose exec -T party0 bash -lc "ps aux | sed -n '1,200p'"
docker compose exec -T party1 bash -lc "ps aux | sed -n '1,200p'"
docker compose exec -T party2 bash -lc "ps aux | sed -n '1,200p'"

docker compose exec -T party0 bash -lc "ss -ltnp | sed -n '1,200p' || ss -ltp || netstat -ltnp"
docker compose exec -T party1 bash -lc "ss -ltnp | sed -n '1,200p' || ss -ltp || netstat -ltnp"
docker compose exec -T party2 bash -lc "ss -ltnp | sed -n '1,200p' || ss -ltp || netstat -ltnp"
```

2. Se existirem processos `mascot-party.x` antigos, matar explicitamente (confirmar PID antes):

```bash
docker compose exec -T party0 bash -lc "pkill -f mascot-party.x || true"
docker compose exec -T party1 bash -lc "pkill -f mascot-party.x || true"
docker compose exec -T party2 bash -lc "pkill -f mascot-party.x || true"
```

3. Verificar se portas ficaram em estado estranho (LISTEN/TIME_WAIT); se necessário, reiniciar o(s) container(s):

```bash
docker compose exec -T party0 bash -lc "ss -ltnp"
docker compose restart party0
```

4. Reiniciar as parties de forma controlada, redirecionando logs para `/tmp` e deixando correr sem timeout (modo detached):

```bash
docker compose exec -T -d party0 bash -lc "cd /mp-spdz && ./mascot-party.x -N 3 -p 0 -ip Config/IPs -IF Inputs/Input dark_auction > /tmp/mascot_p0.log 2>&1"
docker compose exec -T -d party1 bash -lc "cd /mp-spdz && ./mascot-party.x -N 3 -p 1 -ip Config/IPs -IF Inputs/Input dark_auction > /tmp/mascot_p1.log 2>&1"
docker compose exec -T -d party2 bash -lc "cd /mp-spdz && ./mascot-party.x -N 3 -p 2 -ip Config/IPs -IF Inputs/Input dark_auction > /tmp/mascot_p2.log 2>&1"

# Verificar logs iniciais
docker compose exec -T party0 bash -lc "tail -n 200 /tmp/mascot_p0.log || true"
docker compose exec -T party1 bash -lc "tail -n 200 /tmp/mascot_p1.log || true"
docker compose exec -T party2 bash -lc "tail -n 200 /tmp/mascot_p2.log || true"
```

5. Reexecutar a validação E2E, mas sem forçar timeout no wrapper (deixar correr):

```bash
# Opção A: executar parties em três terminais separados, em foreground
docker compose exec -T party0 bash -lc "cd /mp-spdz && ./mascot-party.x -N 3 -p 0 -ip Config/IPs -IF Inputs/Input dark_auction"
# repetir para party1 e party2 em terminais separados

# Opção B: usar o validador Python mas sem timeout (editar/usar --mpc-timeout grande ou executar os comandos manualmente)
```

6. Recolher logs e outputs relevantes (copiar para host):

```bash
docker cp mpc_party_0:/tmp/mascot_p0.log ./logs/mascot_p0.log || docker compose exec -T party0 bash -lc "cat /tmp/mascot_p0.log" > mascot_p0.log
docker cp mpc_party_1:/tmp/mascot_p1.log ./logs/mascot_p1.log || docker compose exec -T party1 bash -lc "cat /tmp/mascot_p1.log" > mascot_p1.log
docker cp mpc_party_2:/tmp/mascot_p2.log ./logs/mascot_p2.log || docker compose exec -T party2 bash -lc "cat /tmp/mascot_p2.log" > mascot_p2.log

docker compose exec -T party0 bash -lc "ps aux | sed -n '1,200p'" > party0_ps.txt
docker compose exec -T party0 bash -lc "ss -ltnp | sed -n '1,200p'" > party0_ss.txt
```

7. Se o problema persistir: reiniciar a engine Docker ou executar o workflow dentro de WSL/Linux (menos problemas de I/O e signals no Windows host).

## Ficheiros para anexar quando pedir ajuda

- `/tmp/mascot_p0.log`, `/tmp/mascot_p1.log`, `/tmp/mascot_p2.log`
- `party0_ps.txt`, `party1_ps.txt`, `party2_ps.txt` (output de `ps aux`)
- `party0_ss.txt`, `party1_ss.txt`, `party2_ss.txt` (output de `ss -ltnp`)
- `Inputs/Input-P0-0` (exemplo de input usado)

## Ficheiros relevantes no repositório

- [MILESTONE_2_REPORT.md](MILESTONE_2_REPORT.md)
- [scripts/validate_end_to_end.py](scripts/validate_end_to_end.py)
- [scripts/generate_inputs.py](scripts/generate_inputs.py)
- [simulator/dark_auction_sim.py](simulator/dark_auction_sim.py)
- [dark_auction.mpc](dark_auction.mpc)
- [Inputs/Input-P0-0](Inputs/Input-P0-0)

---

Se quiseres, executo já os passos (matar instâncias, reiniciar parties com logs e recolher os primeiros 200 linhas de cada log). Diz apenas para avançar.
