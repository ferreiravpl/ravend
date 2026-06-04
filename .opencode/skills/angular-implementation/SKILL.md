---
name: angular-implementation
description: Padrões e checklist para implementar mudanças em codebases Angular.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Angular respeitando a convenção real da aplicação.

## Quando usar
Use quando a task envolver frontend Angular.

## Quando não usar
Não use para Quarkus ou Spring.
Não use para impor um estilo de frontend diferente do padrão consolidado no projeto.

## O que observar primeiro
- organização de componentes e serviços
- padrão de fluxo de dados e reatividade
- convenção de templates
- padrão de formulários e validação
- estilo de testes e naming
- estrutura modular já presente na aplicação

## Princípios
- manter componente com responsabilidade clara;
- evitar lógica excessiva no template;
- evitar duplicar regra já existente em service ou utilitário;
- seguir o fluxo reativo que o projeto já usa;
- preferir mudança pequena e previsível.

## Checklist de implementação
1. O componente continua coeso.
2. O template não ficou excessivamente complexo.
3. Serviços e utilitários foram reutilizados quando possível.
4. O fluxo de dados segue o padrão já adotado.
5. A alteração respeita o padrão de formulários do projeto.
6. A mudança não espalha estado sem necessidade.
7. Testes foram ajustados quando necessário.
8. A solução continua legível.

## Armadilhas comuns
- lógica demais no template
- componente inchado
- acoplamento direto indevido com detalhe de infraestrutura
- fluxo reativo inconsistente com o resto do projeto
- duplicação de regra em componente e service

## Saída esperada
- componente ou service coerente com a base
- template legível
- baixo acoplamento adicional
- testes coerentes com a mudança
