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

## Observação: saída recente do `party1` (execução em background)

Registo da saída observada no `party1` durante a execução do programa `dark_auction`:

```
Using statistical security parameter 40
No modulus found in Player-Data//3-p-128/Params-Data, generating 128-bit prime
Using prime modulus 170141183460469231731687303715885907969
Setup took 6.83478 seconds.
Compiler: ./compile.py dark_auction
	786 triples of SPDZ gfp left
	949 bits of SPDZ gfp left
Detailed costs:
	   120 integer inputs
       9134214 integer multiplications
      34409042 integer openings
Spent 14.907 seconds (293.653 MB, 11154 rounds) on the online phase and 10550.1 seconds (668873 MB, 547182 rounds) on the preprocessing/offline phase.
Communication details:
Broadcasting 0.957284 MB in 36315 rounds, taking 4.55879 seconds
Exchanging one-to-one 562528 MB in 137340 rounds, taking 1162.55 seconds
Partial broadcasting 1.81558 MB in 69830 rounds, taking 82.804 seconds
Receiving directly 825.221 MB in 37246 rounds, taking 60.7442 seconds
Receiving one-to-one 105811 MB in 120179 rounds, taking 0.00918179 seconds
Sending directly 825.217 MB in 37244 rounds, taking 2.7062 seconds
Sending one-to-one 105811 MB in 120178 rounds, taking 0.00196255 seconds
Sending to all 0.00192 MB in 1 rounds, taking 0.000103075 seconds
Sending/receiving 9.6e-05 MB in 3 rounds, taking 0.000862694 seconds
CPU time = 19472.1
The following benchmarks are including preprocessing (offline phase).
Time = 10565 seconds 
Data sent = 669167 MB in ~558336 rounds (party 1 only)
Global data sent = 2.00833e+06 MB (all parties)
Actual preprocessing cost of program:
  Type int
       9134214        Triples
       8031051           Bits
	   360   Input tuples (120 120 120)
This program might benefit from some protocol options.
Consider adding the following at the beginning of your code:
	program.use_edabit(True)
Coordination took 4.14522 seconds
Command line: ./mascot-party.x -N 3 -p 1 -ip Config/IPs -IF Inputs/Input -v dark_auction
```

### Interpretação rápida

- O `party1` completou a fase de pré-processamento offline que dominou o tempo total (~10550s ≈ 2.93 horas) e consumiu centenas de GB de dados.
- O `Global data sent` reporta ~2.0e+06 MB (~2 TB) agregados entre as parties — isto confirma que o programa é muito pesado em termos de triples/abertura e comunicações.
- A sugestão `program.use_edabit(True)` aparece no output e é um ponto de partida para reduzir custos de pré-processamento quando se fazem muitas operações fix-point/divisão/bit-decomposition.

### Ações recomendadas imediatas

1. Aguardar que `party0` e `party2` completem — recolher igualmente os seus logs em `/tmp/mascot_p0.log` e `/tmp/mascot_p2.log`.
2. Copiar os três ficheiros de log para o host e anexá-los aqui para análise mais profunda (ou executar `tail -n 500` para cada um).
3. Considerar alterações no código para reduzir custos offline antes de executar grandes benchmarks: por exemplo, adicionar `program.use_edabit(True)` no início de `dark_auction.mpc`, reduzir o intervalo de preços escaneado, ou diminuir `N_ORDERS` para testes iterativos.
4. Para benchmarking real, usar menos rounds/protocols ou testar em uma máquina Linux/WSL com mais recursos e sem limitações de I/O do Windows.

### Comandos úteis para obter logs agora

```bash
docker compose exec -T party0 bash -lc "tail -n 500 /tmp/mascot_p0.log || true"
docker compose exec -T party1 bash -lc "tail -n 500 /tmp/mascot_p1.log || true"
docker compose exec -T party2 bash -lc "tail -n 500 /tmp/mascot_p2.log || true"

docker cp mpc_party_0:/tmp/mascot_p0.log ./logs/mascot_p0.log || true
docker cp mpc_party_1:/tmp/mascot_p1.log ./logs/mascot_p1.log || true
docker cp mpc_party_2:/tmp/mascot_p2.log ./logs/mascot_p2.log || true
```

---

Atualizei este ficheiro com os detalhes do `party1`. Se queres, prossigo e recolho os logs `p0/p2` agora e faço um sumário comparativo.

## Saídas recentes adicionadas

### `party2` (resumo observado)

```
Using statistical security parameter 40
No modulus found in Player-Data//3-p-128/Params-Data, generating 128-bit prime
Using prime modulus 170141183460469231731687303715885907969
Setup took 0.42099 seconds.
Compiler: ./compile.py dark_auction
				786 triples of SPDZ gfp left
				949 bits of SPDZ gfp left
Detailed costs:
					 120 integer inputs
			 9134214 integer multiplications
			34409042 integer openings
Spent 15.3835 seconds (293.653 MB, 11154 rounds) on the online phase and 10549.6 seconds (668873 MB, 512847 rounds) on the preprocessing/offline phase.
Communication details:
Broadcasting 0.957284 MB in 36315 rounds, taking 4.32357 seconds
Exchanging one-to-one 562528 MB in 137340 rounds, taking 1173.43 seconds
Partial broadcasting 1.81558 MB in 69830 rounds, taking 90.9836 seconds
Receiving directly 825.221 MB in 37246 rounds, taking 61.945 seconds
Receiving one-to-one 105811 MB in 103012 rounds, taking 0.0068339 seconds
Sending directly 825.217 MB in 37244 rounds, taking 2.36867 seconds
Sending one-to-one 105811 MB in 103010 rounds, taking 0.00210342 seconds
Sending to all 0.00192 MB in 1 rounds, taking 0.000129474 seconds
Sending/receiving 9.6e-05 MB in 3 rounds, taking 0.000779256 seconds
CPU time = 19483.3
The following benchmarks are including preprocessing (offline phase).
Time = 10565 seconds 
Data sent = 669167 MB in ~524001 rounds (party 2 only)
Global data sent = 2.00833e+06 MB (all parties)
Actual preprocessing cost of program:
	Type int
			 9134214        Triples
			 8031051           Bits
					 360   Input tuples (120 120 120)
This program might benefit from some protocol options.
Consider adding the following at the beginning of your code:
				program.use_edabit(True)
Coordination took 4.19834 seconds
Command line: ./mascot-party.x -N 3 -p 2 -ip Config/IPs -IF Inputs/Input -v dark_auction
```

### `party0` (resumo observado)

```
Using statistical security parameter 40
No modulus found in Player-Data//3-p-128/Params-Data, generating 128-bit prime
Using prime modulus 170141183460469231731687303715885907969
Setup took 13.0082 seconds.
Asset 0: clearing_price=104.5 remainder=1 traded=15
	Party 0 fill=8.25
	Party 1 fill=3.75003
	Party 2 fill=3.00002
Asset 1: clearing_price=202 remainder=0 traded=15
	Party 0 fill=6
	Party 1 fill=4.16667
	Party 2 fill=5.83331
Asset 2: clearing_price=52.5 remainder=1 traded=15
	Party 0 fill=2.36842
	Party 1 fill=8.68422
	Party 2 fill=3.94736
Compiler: ./compile.py dark_auction
				786 triples of SPDZ gfp left
				949 bits of SPDZ gfp left
Detailed costs:
					 120 integer inputs
			 9134214 integer multiplications
			34409042 integer openings
Spent 15.3087 seconds (587.174 MB, 19174 rounds) on the online phase and 10549.7 seconds (669405 MB, 647985 rounds) on the preprocessing/offline phase.
Communication details:
Broadcasting 0.957284 MB in 36315 rounds, taking 4.52435 seconds
Exchanging one-to-one 562528 MB in 137340 rounds, taking 1159.81 seconds
Partial broadcasting 1.81558 MB in 69830 rounds, taking 78.9647 seconds
Receiving directly 1650.44 MB in 74490 rounds, taking 58.6406 seconds
Receiving one-to-one 105811 MB in 137346 rounds, taking 0.0105263 seconds
Sending directly 1650.43 MB in 74488 rounds, taking 4.76121 seconds
Sending one-to-one 105811 MB in 137346 rounds, taking 0.00175474 seconds
Sending to all 0.00192 MB in 1 rounds, taking 0.000108989 seconds
Sending/receiving 9.6e-05 MB in 3 rounds, taking 0.000557194 seconds
CPU time = 19495.4
The following benchmarks are including preprocessing (offline phase).
Time = 10565 seconds 
Data sent = 669992 MB in ~667159 rounds (party 0 only)
Global data sent = 2.00833e+06 MB (all parties)
Actual preprocessing cost of program:
	Type int
			 9134214        Triples
			 8031051           Bits
					 360   Input tuples (120 120 120)
This program might benefit from some protocol options.
Consider adding the following at the beginning of your code:
				program.use_edabit(True)
Coordination took 4.16994 seconds
Command line: ./mascot-party.x -N 3 -p 0 -ip Config/IPs -IF Inputs/Input -v dark_auction
```

### Interpretação adicional

- Os três parties completaram o pré-processamento offline massivo (≈10565s) e relatam comunicações agregadas na ordem de TBs; isto confirma que o programa exige muitos recursos e que as runs bloqueantes são normais para este tamanho.
- O `party0` também imprime os resultados finais (clearing_price/traded/fills) com valores fraccionários — isto indica que a saída do MPC foi formatada com decimais (provavelmente devido à forma como se converteu internamente para apresentação). Os valores de `fill` mostrados têm casas decimais (ex.: 8.25), mas a lógica do relatório deve comparar inteiros/strings; o validador Python deve extrair e normalizar estes valores antes de comparar com o simulador.
- A sugestão `program.use_edabit(True)` aparece em todos os logs e é recomendada para reduzir custo de pré-processamento em operações intensivas.

### Próximos passos sugeridos

1. Copiar os ficheiros `/tmp/mascot_p0.log`, `/tmp/mascot_p1.log`, `/tmp/mascot_p2.log` para o host e anexá-los ao issue/review.
2. Ajustar o validador para extrair número de `fill` com tolerância a floats (por exemplo arredondar ou converter para int quando apropriado) antes de comparar.
3. Considerar otimizações no `dark_auction.mpc` para reduzir pré-processamento: `program.use_edabit(True)`, restringir a faixa de preços, ou testar com menor `N_ORDERS`.

Se quiseres, faço já a cópia dos logs para `./logs/` no host e preparo um diff de comparação entre simulador e MPC extraindo/normalizando os fills.
