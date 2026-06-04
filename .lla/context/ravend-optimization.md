# Otimização do Harness Ravend

Quando o usuário pedir para otimizar o Ravend, avaliar:

## Critérios
- o fluxo resolve o problema real?
- há agentes demais?
- há skills grandes demais?
- há commands que duplicam lógica?
- há contexto estável no lugar errado?
- há opportunity de simplificação?
- o handoff está claro?
- o custo de contexto está alto demais?
- a knowledge está seletiva o bastante?
- existe alternativa menor e mais rastreável?

## Preferências
- skills pequenas e específicas;
- agentes com papel claro;
- commands como launcher;
- manifests curtos e objetivos;
- contexto estável separado do contexto variável;
- resumos incrementais em vez de contexto longo.

## Antipadrões
- prompt monolítico;
- excesso de agentes;
- excesso de texto duplicado;
- carregar o repo inteiro sempre;
- criar automação só por criar;
- confundir complexidade com robustez.
