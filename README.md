# abecmed-watcher

Avisa no celular quando o catálogo do bot da ABECMED muda — flor nova, óleo
voltando ao estoque, preço diferente.

Só Python 3, sem instalar dependência nenhuma.

## Passo a passo

**1. Instale o app.** Procure por **ntfy** na Play Store ou App Store. Grátis,
sem cadastro. É por ele que os avisos chegam.

**2. Baixe o projeto.** Botão verde **Code → Download ZIP**, extraia numa pasta.
No Windows, instale o Python de [python.org](https://python.org) marcando
**"Add Python to PATH"** — sem essa caixinha nada funciona. No Ubuntu e macOS
já vem de fábrica.

**3. Configure.** Rode `configurar.bat` (Windows, dois cliques) ou
`./configurar.sh` (Linux/macOS). Ele pede seu CPF de associado e o canal de
avisos — aperte Enter no canal que ele sorteia um nome seguro. **No fim, abra o
ntfy, toque no + e assine o nome que ele mostrar.**

**4. Rode.** `run.bat` ou `./run.sh`. O celular apita com o catálogo atual — é
a confirmação de que funcionou. Depois disso, **só avisa quando muda**.

Para deixar ligado sozinho: `run-loop.bat` ou `./run.sh --loop`. Verifica a
cada 7–12 minutos (sorteado) até você fechar a janela ou apertar Ctrl+C.

| | Windows | Linux / macOS |
|---|---|---|
| configurar | `configurar.bat` | `./configurar.sh` |
| rodar uma vez | `run.bat` | `./run.sh` |
| modo contínuo | `run-loop.bat` | `./run.sh --loop` |
| testar sem notificar | — | `./run.sh --dry-run` |

> Tópicos do ntfy.sh são públicos: quem souber o nome recebe seus avisos.
> Aceite o nome sorteado pelo configurador.

## Que aviso chega quando

Flor esgota em horas; typo corrigido no óleo, não. Os avisos têm pesos
diferentes por isso:

| Mudou | Aviso | Prioridade ntfy |
|---|---|---|
| a tela de **flores** | 🌸 Flor nova na ABECMED | **5** — toca mesmo no silencioso |
| óleo, concentrado ou só o texto | ABECMED mudou: *seção* | 2 — chega calado |
| primeira execução | abecmed-watch ativo | 3 |
| o fluxo quebrou | abecmed-watch quebrou | 4 |

A comparação é por seção, então o título já diz onde mexeram. O corpo traz as
linhas novas em destaque e o catálogo inteiro embaixo.

## config.ini

Criado pelo configurador, editável no Bloco de Notas:

```ini
[abecmed]
cpf = 12345678900
topico = abecmed-jepv8l0v

intervalo_min = 7
intervalo_max = 12
```

Rodar o configurador de novo é seguro: Enter mantém o valor atual.

**Não versione** — tem seu CPF. Já está no `.gitignore`. As variáveis de
ambiente `ABECMED_CPF` e `NTFY_TOPIC`, se existirem, têm prioridade.

Apagar o `estado.json` faz a próxima execução mandar o catálogo inteiro de novo
— útil pra reconfirmar que está funcionando sem esperar o estoque mudar. Ele
também guarda um campo `quebrado`, que é como o aviso de falha não vira spam
quando cada verificação roda num processo novo (o caso do GitHub Actions).

## Rodar na nuvem (recomendado)

Sem servidor, sem deixar o PC ligado. São três peças, e a divisão de trabalho
entre elas é a parte que importa:

| Peça | Papel |
|---|---|
| **cron-job.org** | o relógio — chama a API do GitHub a cada 10 min |
| **GitHub Actions** | o executor — roda o `bot.py` e guarda o `estado.json` |
| **healthchecks.io** | a testemunha — percebe quando as duas acima param |

**Por que o relógio é externo.** O `schedule:` do Actions é best-effort: a
documentação do próprio GitHub diz que execução agendada pode atrasar sob carga
e **pode ser descartada**. Na prática, aqui, foram 40 min num fork e 20 min num
repositório standalone com zero disparos. Para flor que esgota em horas isso não
é cadência, é sorte. O `schedule:` continua no workflow, mas como rede de
segurança — não como fonte da verdade.

**Por que a testemunha.** Monitor parado e monitor sem novidade produzem
exatamente o mesmo silêncio no celular. Um sistema não consegue avisar que
morreu; quem percebe o silêncio tem que estar de fora dele.

### Montando

1. Crie um repositório seu (público — Actions é ilimitado em repo público, e o
   que fica visível é só o catálogo da associação). **Não use um fork:** o
   GitHub não dispara `schedule` em repositório forkado.
2. **Settings → Secrets and variables → Actions**, três secrets:
   - `ABECMED_CPF` — seu CPF de associado
   - `NTFY_TOPIC` — o tópico do ntfy
   - `HEALTHCHECK_URL` — a Ping URL do healthchecks (opcional; sem ela o passo
     do watchdog fica inerte)
3. **Settings → Actions → General → Workflow permissions**: marque
   **Read and write** (sem isso o commit do estado falha com 403).
4. **healthchecks.io**: Add Check, Schedule `Simple`, Period `10 minutes`,
   Grace `15 minutes`. Em Integrations, adicione **ntfy** apontando pro mesmo
   tópico, priority alta no evento "down".
5. **cron-job.org**: um cronjob a cada 10 min. Use o botão
   **IMPORT FROM CURL** com o comando abaixo, trocando o token:

```bash
curl -X POST https://api.github.com/repos/SEU_USUARIO/SEU_REPO/dispatches \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -d '{"event_type":"check"}'
```

O token é um fine-grained PAT com **Contents: Read and write** apenas no
repositório do monitor. Anote a validade: quando vencer, o monitor para — e é
o healthchecks que vai te contar.

Um **TEST RUN** que devolve **204 No Content** é sucesso.

### Conferindo que está de pé

Verificação agendada é fácil de configurar e fácil de acreditar que funciona.
Três provas que valem mais que a configuração parecer certa:

- **roda sozinho?** Na aba Actions, procure um run `repository_dispatch` que
  você não disparou. Enquanto todos tiverem dono, nada está automático.
- **o watchdog avisa?** `curl https://hc-ping.com/SEU_UUID/fail` deve fazer o
  celular tocar em segundos. Depois `curl https://hc-ping.com/SEU_UUID`
  restaura. Watchdog não testado é decoração.
- **hibernação:** o `schedule:` de reserva é desligado após 60 dias sem
  atividade humana no repositório. O gatilho principal não depende disso.

## Como funciona

Abre uma sessão no Typebot da associação e navega sozinho: paciente → CPF →
menu → flores → *voltar* → concentrados → *voltar* → óleo. Junta o texto das
telas, compara com a rodada anterior (`estado.json`), notifica se mudou.

**Não interpreta nome nem preço** — compara o texto inteiro. Menos elegante,
muito mais difícil de quebrar: o aviso entrega o texto literal que o bot
escreveu, já legível. Em compensação, qualquer alteração dispara notificação,
inclusive um typo corrigido ou emoji trocado.

Precisa do CPF de um **associado** — é assim que o bot identifica quem está
falando. Sem CPF válido a conversa não passa da segunda tela. As requisições
usam cabeçalhos de navegador; não burla autenticação (o bot não tem nenhuma),
serve pra não ser barrado pela proteção anti-bot da hospedagem.

## Quando quebrar

Vai quebrar quando a associação mexer no fluxo. Chega um aviso
**"abecmed-watch quebrou"** com as opções que não foram reconhecidas — uma vez
por sequência de falhas, não a cada ciclo. O conserto costuma ser um regex na
tabela `CATEGORIAS`, dentro do `bot.py`:

```python
CATEGORIAS = [
    ("FLORES", r"flor"),
    ("CONCENTRADOS", r"concentrad"),
    ("OLEO", r"[óo]leo"),
]
```

Só flor é obrigatória: se concentrado ou óleo sumirem do menu, a verificação
segue sem eles. A tela de boas-vindas já avisou que flor pode migrar pra dentro
do fluxo de óleo (`"Quero adquirir óleo" → "Incluir flor"`); o script tenta
esse desvio sozinho antes de desistir.

---

MIT. Sem vínculo com a ABECMED — ferramenta de conveniência, de associado para associado.
