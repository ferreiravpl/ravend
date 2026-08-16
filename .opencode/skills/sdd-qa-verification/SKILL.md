---
name: sdd-qa-verification
description: Verifica a mudança com build real, testes com escopo restrito, lint gate e guardrail validators.
compatibility: opencode
---
## Objetivo
Validar tecnicamente a task ativa com build real, testes determinísticos, lint gate e guardrail validators.

## Quando usar
Use após implementação ou quando a solicitação for QA-only.

## Procedimento

### Step 0 — Detectar perfil do projeto

Identifique o build system e estrutura:

- **Maven**: procurar `pom.xml` na raiz e em subdiretórios.
- **Gradle**: procurar `build.gradle` ou `build.gradle.kts`.
- **npm/pnpm/yarn**: procurar `package.json`, `pnpm-lock.yaml`, `yarn.lock`.
- **Multi-module**: verificar se há múltiplos `pom.xml` ou `settings.gradle*`.

Registre o perfil como string (ex.: `maven-multi`, `gradle-single`, `npm-angular`).

### Step 1 — Stack detection

- Se o input contiver `stacks`, use-o.
- Caso contrário, derive do diff:
  - Arquivos `.java`, `.kt` → `java`
  - Arquivos `.ts`, `.html` em projeto Angular → `angular`
  - Ambos → `java,angular`

### Step 2 — Build Java

Apenas se stack `java` foi detectada.

1. Identifique módulos afetados pelo diff (diretórios com `pom.xml` ou `build.gradle*` que contenham arquivos modificados).
2. Execute build com escopo restrito:
   - **Maven**: `timeout 300 mvn compile -pl <modulo> -am -DskipTests -q`
   - **Gradle**: `timeout 300 ./gradlew :<modulo>:compileJava --quiet`
3. Exit code 0 = PASS. Qualquer outro = FAIL com `error_type: BUILD_ERROR`.

### Step 3 — Testes Java

Apenas se stack `java` foi detectada e build passou.

1. Derive classes de teste dos módulos afetados:
   - Para cada arquivo `X.java` modificado, procure `XTest.java` ou `XIT.java` no mesmo módulo.
2. Execute testes com escopo restrito:
   - **Maven**: `timeout 180 mvn test -pl <modulo> -am -Dtest=Classe1,Classe2 -q`
   - **Gradle**: `timeout 180 ./gradlew :<modulo>:test --tests "Classe1" --tests "Classe2" --quiet`
3. Exit code 0 = PASS. Qualquer outro = FAIL com `error_type: TEST_FAILURE`.
4. Extraia `tests_passed` e `tests_failed` do output do runner.

### Step 4 — Build Angular

Apenas se stack `angular` foi detectada.

1. Localize `angular.json` para identificar o projeto frontend.
2. Execute: `timeout 300 npm run build --prefix <diretório-do-angular>`
3. Exit code 0 = PASS. Qualquer outro = FAIL com `error_type: BUILD_ERROR`.

### Step 5 — Testes Angular

Apenas se stack `angular` foi detectada e build passou.

1. Execute: `timeout 180 npx ng test --watch=false`
2. Exit code 0 = PASS. Qualquer outro = FAIL com `error_type: TEST_FAILURE`.
3. Extraia `tests_passed` e `tests_failed` do output do Karma/Jest.

### Step 6 — Lint gate

Execute linting para as stacks detectadas.

**Checkstyle (Java)**:
1. Procure `checkstyle.xml` no projeto-alvo (diretório do módulo afetado). Se não existir, procure na raiz.
2. Se encontrado, execute:
   - **Maven**: `mvn checkstyle:check -pl <modulo> -am -q`
   - **Gradle**: `./gradlew :<modulo>:checkstyleMain --quiet`
3. Se não encontrado, skip com nota e `lint_violations: 0`.

**ESLint (Angular)**:
1. Verifique se `.eslintrc*` ou `eslint.config.*` existe no diretório do Angular.
2. Se encontrado, execute: `npx eslint . --format compact 2>/dev/null`
3. Se não encontrado, skip com nota e `lint_violations: 0`.

Exit code 0 = sem violações. Qualquer outro = FAIL com `error_type: LINT_FAILURE`.
Conte violações do output e registre em `lint_violations`.

### Step 7 — Guardrail validators

Valide guardrails sobre os arquivos do diff (não sobre todo o projeto).

**class-size**: nenhuma classe Java pode exceder 150 linhas.
```bash
find . -name "*.java" -path "*/src/main/*" | while read f; do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 150 ]; then
    echo "VIOLATION: $f has $lines lines (max 150)"
  fi
done
```

**code-formatting**: nenhuma linha pode exceder 140 caracteres.
```bash
find . -name "*.java" -path "*/src/main/*" | while read f; do
  awk 'length > 140 { print "VIOLATION: " FILENAME ":" NR " has " length " chars (max 140)" }' "$f"
done
```

**unit-test-naming**: nomes de métodos de teste devem seguir snake_case.
```bash
find . -name "*Test.java" -path "*/src/test/*" | while read f; do
  grep -nP 'public\s+void\s+[a-z][a-zA-Z0-9]*\(' "$f" | \
  grep -vP 'public\s+void\s+[a-z]+(_[a-z0-9]+)+\(' | \
  grep -vP 'public\s+void\s+(setUp|tearDown|before|after)\('
done
```

Conte violações e registre em `guardrail_violations`.
Se `guardrail_violations > 0`, `qa_status = FAIL` e `error_type = LINT_FAILURE`.

### Step 8 — Output e relatório

1. Monte o output JSON conforme `.lla/manifests/schemas/qa-output.schema.json`.
2. Salve relatório em `.lla/sdd/current/{task_id}/qa-report.md` com:

O `task_id` é fornecido pelo orchestrator no prompt ou handoff.
   - Perfil detectado
   - Stacks validadas
   - Resultado de cada step (PASS/FAIL/SKIP)
   - Output JSON final

## Regras de determinismo

- `qa_status` é determinado **exclusivamente** por exit codes.
- Exit code 0 = PASS. Qualquer outro = FAIL.
- Timeout (exit code 124 do comando `timeout`) = FAIL com `error_type: TIMEOUT`.
- Se múltiplos steps falharem, o primeiro erro determina `error_type`.

## Fallback graceful

- Se ferramenta de lint (checkstyle, ESLint) não estiver disponível, skip com nota no `detail` e `lint_violations: 0`.
- Se build system não for detectado, registre `profile: "unknown"` e pule steps de build/teste com SKIP.
- Nunca falhe por falta de ferramenta opcional.

## Escopo restrito

- Build e testes são executados apenas nos módulos afetados pelo diff.
- Guardrails são validados apenas sobre arquivos modificados.
- Não execute build/teste full sem necessidade.
