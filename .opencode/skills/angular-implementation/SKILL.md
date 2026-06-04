---
name: angular-implementation
description: Padrões e checklist para implementar mudanças em codebases Angular.
compatibility: opencode
---
## Objetivo
Aplicar boas práticas de implementação em Angular.

## Quando usar
Use quando a task envolver frontend Angular.

## Verificar antes de implementar
- padrão de organização já adotado no projeto
- uso consistente de componentes, serviços e modelos
- padrão de estado e fluxo reativo já existente
- consistência do template com o restante da aplicação
- cobertura de testes conforme o padrão do projeto

## Armadilhas comuns
- mover lógica demais para template
- criar componente grande demais
- quebrar padrão de fluxo reativo já usado
- duplicar lógica que já existe em serviço ou utilitário

## Procedimento
1. Ler convenções e stack do projeto.
2. Ler componentes e serviços vizinhos.
3. Reusar o padrão predominante.
4. Implementar a menor mudança segura.
