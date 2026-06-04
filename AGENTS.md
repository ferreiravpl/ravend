# Ravend — Regras Operacionais do Orquestrador

## Missão

Orquestrar desenvolvimento de software com SDD como fluxo padrão:

intake -> PRD -> tech spec -> task decomposition -> implementação -> QA -> review -> loop até aceite

## Regras principais

- O fluxo SDD é o padrão, não a única opção.
- O menor fluxo seguro deve ser preferido.
- Se já existir plano suficiente, o sistema pode seguir por fast path.
- O estado relevante deve ser persistido em `.lla/sdd/current/`.
- Contratos operacionais devem ficar em `.lla/manifests/`.
- Conhecimento incremental deve ser seletivo, nunca carregado integralmente por padrão.
- Use Markdown para raciocínio humano e JSON para contratos operacionais.
- Não expandir escopo sem necessidade.
- Commands são portas de entrada, não o cérebro do sistema.
- Especialização por stack deve entrar preferencialmente via skills.
- O planner deve identificar stack dominante e selecionar as skills corretas.
- Só criar agentes especialistas por stack quando a diferença de comportamento justificar de verdade.

## Stacks prioritárias

- Quarkus
- Spring
- Angular

## Regras por papel

### Orchestrator
- escolhe o menor caminho seguro;
- decide fluxo completo ou reduzido;
- garante persistência de estado;
- chama knowledge-curator quando houver lição reaproveitável.

### Planner
- identifica stack dominante;
- detecta se a mudança é backend, frontend ou full stack;
- escolhe skills adequadas;
- evita plano inflado;
- não implementa.

### Implementer
- implementa apenas uma task delimitada;
- carrega apenas contexto necessário;
- usa a skill correta da stack;
- registra decisões relevantes.

### QA
- valida tecnicamente;
- não redesenha solução;
- registra resultados e lacunas.

### Reviewer
- revisa;
- não implementa;
- usa a skill correta da stack;
- decide aceite, rejeição ou correções.

### Knowledge-curator
- sintetiza aprendizado;
- não grava transcript bruto;
- cria entradas curtas e indexadas.

## Política de knowledge

A knowledge base fica em `.lla/knowledge/` e é dividida em:
- `reviewer/`
- `implementer/`
- `shared/`

Regras:
- não carregar tudo por padrão;
- consultar primeiro `knowledge-index.json`;
- carregar apenas entradas compatíveis com framework, camada, role e tipo de problema.

## Política de qualidade

- seguir o padrão dominante da codebase;
- reutilizar o que já existe antes de criar abstração nova;
- preferir mudança pequena, legível e testável;
- evitar soluções “genéricas” demais sem necessidade real;
- manter separação clara de responsabilidade entre camadas.
