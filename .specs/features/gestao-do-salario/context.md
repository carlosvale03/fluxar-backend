# Gestão do salário Context

**Gathered:** 2026-09-26
**Spec:** `.specs/features/gestao-do-salario/spec.md`
**Status:** Spec aprovada; design e tasks aprovados em 2026-10-10

---

## Feature Boundary

O plano de divisão do salário, a simulação, o aviso ao lançar o salário, a geração em um clique das transferências e dos aportes do plano, com confirmação forte, e o desfazer da divisão inteira. Mover dinheiro de verdade no banco e reconhecer o salário pelo crédito bancário dependem do Open Finance (PROP-05) e ficam de fora.

---

## Implementation Decisions

### Geração, confirmação e desfazer

- O usuário gera todas as transações do plano com um único clique, depois de uma confirmação forte, e pode desfazer a geração inteira (decisão na aprovação da PROP-01).

### Transações geradas

- Nascem efetivadas na hora (AD-026).

### Regras do plano

- Cada parte tem um valor fixo ou um percentual do salário, numa ordem de prioridade; o que sobra fica livre na conta do salário.

### Quando a divisão aparece

- A tela da gestão do salário fica disponível a qualquer momento, para simulações e para divisões de verdade.
- Quando o usuário lança uma receita de salário, o app mostra na hora a opção de dividir e os benefícios de fazer isso.

### Como o plano começa

- Sugestão a partir do histórico, sem fixar no 50/30/20: três modelos pré-configurados da literatura, do mais geral ao mais detalhado, com o 50/30/20 entre eles, e a opção personalizada.

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-26.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Quais são os três modelos e as partes de cada um, os destinos e o destino inicial das partes.
- Categorias de salário, um plano por usuário e recebimentos a dividir.
- Salário menor que o plano, centavos e ajuste na revisão.
- Forma da confirmação forte, data das transações e prazo e condições do desfazer.
- Aviso na importação, referências do mês, trava de plano, recebimento alterado depois da divisão e texto dos benefícios.

---

## Specific References

Modelos de divisão e as obras de origem:

| Modelo | Obra | Partes |
| ------ | ---- | ------ |
| Pague-se primeiro | George S. Clason, *O Homem Mais Rico da Babilônia* (1926): guardar ao menos um décimo de tudo o que se ganha | Guardar 10% |
| 50/30/20 | Elizabeth Warren e Amelia Warren Tyagi, *All Your Worth* (2005), <https://www.simonandschuster.com/books/All-Your-Worth/Elizabeth-Warren/9780743269889> | Essenciais 50%, Dispensáveis 30% e Guardar 20% |
| Seis potes | T. Harv Eker, *Os Segredos da Mente Milionária* (2005), <https://www.harveker.com/blog/6-step-money-managing-system/> | Necessidades 55%, Liberdade financeira 10%, Poupança para gastos futuros 10%, Educação 10%, Diversão 10% e Doações 5% |

Código de hoje:

- A transferência é atômica e cria as duas pontas com o mesmo `transfer_id` (`transactions/services.py:49-72`), mas a API não confere se origem e destino são diferentes nem se o valor é positivo (`transactions/serializers.py:248-261`).
- O aporte numa meta é uma transferência para a conta-cofrinho mais um `GoalDeposit` (`goals/services.py:43-68`), e a meta já calcula quanto guardar por mês até a data-alvo (`goals/services.py:137-170`).
- Toda transação criada numa conta-cofrinho é repartida entre as metas ativas dela, sem olhar o status (`goals/signals.py:11-90`); a SALARIO-33 pede que o aporte da divisão entre só na meta escolhida.
- Excluir uma transação apaga o `GoalDeposit` mas não devolve o valor da meta (`goals/signals.py:92-102`, FIN-09); a SALARIO-46 pede que o desfazer devolva.
- A exclusão em lote só existe por série recorrente ou por transferência (`transactions/views.py:162-177`).
- "Salário" é uma categoria de receita padrão como as outras (`transactions/signals.py:9`), e `User.monthly_income` não é lido por nenhuma regra (`api/models.py:56`).
- A interface efetiva uma ocorrência pendente pelo botão "Efetivar" (`fluxar-frontend/src/app/(app)/transacoes/page.tsx:929-938`), que envia `PATCH {status: "COMPLETED"}` (`:261-270`).

---

## Deferred Ideas

- Aviso fixo no dashboard enquanto houver salário sem dividir.
- Lembrete por e-mail ou push no dia do pagamento.
- Mais de um plano por usuário, como um plano para o 13º salário.
- Iniciar as transferências por Pix direto do app, com o Open Finance (PROP-05).
