# Importacao Context

**Gathered:** 2026-09-25
**Spec:** `.specs/features/importacao/spec.md`
**Status:** Spec aprovada; design não iniciado

---

## Feature Boundary

Importação de OFX, CSV e XLSX: como cada linha vira receita, despesa ou transferência, como valores e datas no formato brasileiro são lidos, o que a resposta informa sobre linhas gravadas, ignoradas e rejeitadas, e os limites do arquivo. A exportação em PDF e XLSX fica de fora.

---

## Implementation Decisions

### Linha inválida

- Rejeita só a linha; as válidas são gravadas. A resposta lista cada rejeitada com o número e o motivo.
- Hoje o laço inteiro roda num único `transaction.atomic()` (`data_exchange/services.py:305`), então um erro de banco numa linha desfaz o arquivo inteiro, e a view responde 200 porque testa `created >= 0` (`data_exchange/views.py:105`).

### Tamanho máximo

- 5 MB e 10.000 linhas de dados.
- Hoje não há nenhum limite, e o arquivo, uma cópia em dicionários e todas as transações do usuário são carregados na memória (`data_exchange/services.py:242-246` e `:303`).

### Mesmo arquivo enviado de novo

- Ignora as linhas já importadas, contando as repetições. No OFX, a comparação usa o `FITID`, que hoje não é guardado (o modelo `Transaction` não tem campo para ele).
- Hoje a chave de repetição é data, valor, descrição e tipo (`data_exchange/services.py:60` e `:389`), sem contar repetições: duas compras iguais no mesmo arquivo viram uma só.
- Hoje reimportar um OFX em que tudo já existe responde 400, porque a view exige ao menos uma linha criada (`data_exchange/views.py:39`).

### Agent's Discretion

Nenhuma: as escolhas do agente foram apresentadas como suposições e aprovadas pelo usuário em 2026-09-25.

### Declined / Undiscussed Gray Areas → Assumptions

Registradas na tabela Assumptions & Open Questions da spec e aprovadas junto com ela:

- Formatos aceitos e recusa do `.xls`.
- Separador e codificação do CSV.
- Regra de leitura de valores em texto (AD-009) e formatos de data.
- Palavras aceitas na coluna de tipo.
- Linha de conta não mapeada ou excluída.
- Texto maior que o campo.
- Linhas vazias.
- OFX com mais de uma conta.
- Tempo de resposta de até 30 segundos.
- Número da linha na resposta.
- Coluna de status.

---

## Specific References

- A leitura do valor troca vírgula por ponto e remove o resto (`data_exchange/services.py:323-324`), por isso "1.500" vira 1,50 e "1.234,56" falha.
- A coluna de tipo só reconhece `INCOME`, `RECEITA`, `C` e `CREDITO` (`data_exchange/services.py:368-369`); qualquer outro valor vira despesa.
- Linha sem data ou com data ilegível é pulada sem aviso (`data_exchange/services.py:308-309` e `:317-320`).
- A conta de uma linha não mapeada cai na conta padrão, que pode ser nenhuma (`data_exchange/services.py:276`; `data_exchange/views.py:90`).
- O CSV é lido com `pd.read_csv` sem separador nem codificação (`data_exchange/services.py:104-105` e `:135-136`), o que falha com o CSV do Excel em português.
- A tela oferece `.xls` para planilhas (`fluxar-frontend/src/components/transactions/import-dialog.tsx:284`), mas o backend só tem o `openpyxl`, que lê `.xlsx`.
- A tela já mostra importadas, ignoradas e a lista de erros (`fluxar-frontend/src/components/transactions/import-dialog.tsx:449-475`).
- Os campos têm limite de 255 caracteres na descrição e de 50 no nome de categoria e de tag (`transactions/models.py:13`, `:41` e `:86`).

---

## Deferred Ideas

Nenhuma: a discussão ficou dentro do escopo da feature.
