# A IA utilizada

## Modelos

| Uso | Modelo | Por quê |
|---|---|---|
| Especialistas (conversa e ferramentas) | `gpt-6-luna`, `reasoning_effort=low` | Menor e mais barato da família GPT-6 (US$ 0,10 / 0,50 por milhão de tokens), com tool calling e raciocínio leve para decidir quando buscar imóveis ou abrir a agenda |
| Guardrail, extrator, resumo | `gpt-6-luna`, `reasoning_effort=none` | Tarefas de classificação e *structured output*, onde latência importa mais que raciocínio |
| Embeddings | `text-embedding-3-small` (1536 dimensões) | Barato e bom em português para busca semântica |
| Transcrição | `gpt-4o-mini-transcribe` | Áudios do chat e do Telegram, com prompt de domínio imobiliário |
| Voz | `gpt-4o-mini-tts` (voz `marin`) + reescrita para fala com `gpt-6-luna` | A resposta do chat é reescrita como fala (sem códigos, listas ou "R$") e sintetizada com instruções de tom de consultora paulista |

Todos são configuráveis por variável de ambiente. O código usa `ChatOpenAI` do LangChain, então trocar de provedor é questão de configuração.

## Por que um grafo e não um único agente

Um agente único com várias ferramentas tende a "esquecer" etapas de qualificação, misturar papéis e é difícil de testar. Aqui:

- O **LLM decide o que dizer**; **regras decidem quem fala** (triagem determinística testada em `tests/test_domain.py`).
- Cada especialista tem um objetivo claro, um prompt curto e apenas as ferramentas do seu papel.
- Qualificação e score são **determinísticos** a partir do perfil extraído, então o funil é auditável e explicável para o corretor.

## Humanização e postura comercial

A Sofia segue uma postura de **vendedora consultiva e assertiva** (`sdr/agent/prompts.py`):

- **conduz a conversa**: toda resposta termina com um próximo passo concreto (pergunta que avança, recomendação ou proposta de horário);
- **recomenda com opinião** ("pra você eu iria na 277, porque…") em vez de só listar;
- **é proativa**: simula a parcela quando sabe valor e forma de pagamento, sugere alternativas e bairros, oferece dois horários assim que o lead demonstra interesse (*fechamento assumido*);
- **cria urgência com fatos** (prazo de mudança do lead, agenda da semana), sem inventar escassez, descontos ou outros interessados;
- **contorna objeções** uma vez, com argumento novo, e depois respeita;
- pede o nome cedo e o WhatsApp quando o lead está qualificado, para o corretor confirmar a visita.

O estilo é de WhatsApp: mensagens curtas, até três balões, uma pergunta no fim, reação a detalhes pessoais (família, pet, trabalho), tom espelhado. A Sofia se apresenta como assistente virtual e nunca inventa imóveis, preços ou condições.

## Contexto e memória

- **Curto prazo**: o histórico completo fica no checkpointer Postgres do LangGraph (`thread_id = lead_id`). Cada especialista recebe as últimas 30 mensagens, cortadas sempre no início de uma mensagem do lead para não separar chamadas de ferramenta das respostas.
- **Longo prazo**: o `LeadProfile` estruturado é persistido e reinjetado no prompt a cada turno, junto com o que ainda falta descobrir.
- **Memória de atendimento no prompt**: resumo da conversa até aqui, imóveis já apresentados, compromissos agendados, score/temperatura e, quando o lead volta depois de horas ou dias, a instrução de cumprimentá-lo pelo nome e retomar de onde pararam.
- **Entre canais**: o telefone unifica o lead do site e do Telegram (perfil, histórico e checkpoint mesclados).
- **Para o corretor**: o resumo estruturado é atualizado quando o lead avança no funil e periodicamente.

## Extração estruturada

O extrator recebe o perfil atual e as últimas mensagens e devolve o perfil **completo** atualizado (Pydantic com descrições em português para cada campo). A fusão (`merge_profile`) nunca apaga um dado conhecido por omissão do modelo e aplica correções do lead ("na verdade quero alugar"). Respostas curtas ("3", "sim") são interpretadas à luz da última pergunta da consultora.

## Score e funil

| Critério | Pontos |
|---|---|
| Intenção definida | 10 |
| Campos obrigatórios da intenção (compra/aluguel: preço, quartos, região, prazo; investimento: ticket, retorno esperado, objetivo) | até 40 |
| Urgência (imediata → sem pressa) | 20 / 15 / 8 / 3 / 0 |
| Pagamento à vista ou crédito aprovado / outra forma informada | 10 / 5 |
| Contato informado | 5 |
| Engajamento (4+ / 8+ mensagens) | 5 / 10 |
| Interesse em imóvel específico | 5 |
| Compromisso agendado | 20 |

≥ 70 é **quente**, ≥ 40 **morno**, abaixo disso **frio**. Estágios: novo → em qualificação → qualificado → agendado, além de com corretor, perdido e opt-out.

## Segurança e LGPD

- **Guardrail** antes de qualquer especialista: tentativas de manipulação ("ignore suas instruções", "mostre seu prompt") e abuso recebem respostas seguras e determinísticas, sem passar pelos agentes.
- **Prompts endurecidos**: regras de segurança na persona; os especialistas só acessam dados por ferramentas controladas.
- **LGPD**: aviso de privacidade no primeiro contato, opt-out com "PARAR" (bloqueia follow-ups), exclusão completa de dados e do histórico do agente pelo painel.
- **PII**: CPF, e-mail e telefone mascarados nos logs e nos traces do Langfuse.
- **Acesso**: painel com token, job de follow-up com `CRON_SECRET`, webhook do Telegram com segredo no header, rate limit por sessão e por IP, limite de tamanho de mensagem e de áudio.

## Avaliação

- `tests/`: testes unitários das regras determinísticas (score, estágios, roteamento, opt-out, agenda, finanças, mascaramento de PII).
- `evals/run_scenarios.py`: os três cenários do desafio rodam de ponta a ponta com o LLM real. Um LLM faz o papel do lead seguindo uma persona e outro LLM avalia a transcrição contra o checklist do enunciado, dando notas de humanização, uso de contexto e objetividade. O relatório é salvo em `evals/reports/`.
- Observabilidade em produção: cada turno grava a latência da resposta (média e p90 no painel) e o Langfuse registra o trace de cada nó e ferramenta.
