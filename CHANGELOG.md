# Changelog

Uma linha por mudança, da versão mais nova para a mais antiga. É o que o aviso de atualização mostra; os detalhes ficam na descrição de cada PR.

## 0.6.6
- Testes provam comportamento ou regras: nada de copiar o contrato/config num teste, conferir texto de documentação ou reimplementar regra de negócio no teste.
- O review pede para apagar esses testes (em vez de refatorá-los) e cobra evidência para o que o README afirma sobre comandos e ferramentas.
- Clean code: um record no lugar de interface + implementações, nomes distintos para entrada e recursão, sem Javadoc que repete o nome.
- Contratos de API: campos de request com limite no schema desde a v1, e `Retry-After` em toda resposta 429/503.

## 0.6.5
- Aviso de atualização: ao abrir uma sessão (e no `ravend doctor`), o Ravend compara a versão instalada com a publicada e mostra o que mudou.

## 0.6.4
- Clean code: métodos com o nome do que devolvem, não do mecanismo (`process`, `childrenOf`).
- Clean code: uma operação de pipeline por linha, linha em branco depois de todo bloco com chaves, um tipo por arquivo.
- Clean code: pipeline guardado em variável local vira método com nome.

## 0.6.3
- O CLI do Ravend é chamado pelo caminho literal, sem variável de shell: nada de chamadas negadas em modo headless.

## 0.6.2
- Spec multi-repo: quando um repo sai da branch da spec, o `next` pede o `git switch` em vez de um novo verify.
- O review é registrado por arquivo (`--file`) e funciona em modo headless.
- O reviewer aponta todas as ocorrências de um padrão de uma vez.

## 0.6.1
- Legibilidade antes de métrica: teste dos 30 segundos, lambda conta como aninhamento, sem números mágicos nem pares como dado.

## 0.6.0
- Clean code no build (etapa de refactor e consolidação no fim) e no review (manutenibilidade bloqueia).
- Comentários, identificadores e commits seguem a regra de idioma do repositório; a conversa continua em pt-BR.

## 0.5.1
- A conversa é sempre em pt-BR, mesmo com demanda e código em inglês.

## 0.5.0
- Spec multi-repo: uma demanda implementada em vários repositórios.
