# Personal Harness

Harness local e open source para desenvolvimento assistido por IA com PRD, specs, implementacao, estado recuperavel, controle de custo, quality gates e worktrees gerenciadas pelo Orca.

[English documentation](README.en.md)

## O que ele resolve

O Personal Harness organiza o trabalho da IA sem exigir que todo o contexto seja carregado em cada tarefa.

- `manual-classic` preserva o fluxo detalhado com entrevistas e gates G1 a G4.
- `lean` usa contexto progressivo, smoke checks por feature e revisao final.
- `strict` usa validacao e revisao mais completas por feature.
- PRDs, specs, planos, memoria e estado ficam locais no projeto consumidor.
- GitHub autonomo usa worktree Orca e merge commit.
- O budget gate pode interromper a execucao quando o consumo atingir o limite configurado.
- OpenAI, Anthropic e o modelo herdado pela plataforma podem ser roteados por tarefa.

## Requisitos

- Python 3.10 ou mais recente.
- Git, apenas para os fluxos GitHub.
- Orca CLI, apenas para worktrees e sessoes visiveis gerenciadas pelo Orca.
- Um agente compativel com os arquivos `AGENTS.md` ou `CLAUDE.md`.

O harness continua utilizavel localmente sem Git e sem Orca. O fluxo GitHub autonomo bloqueia com seguranca quando o Orca nao esta disponivel.

## Instalacao em um projeto

Clone este repositorio e execute o instalador apontando para o projeto consumidor:

```bash
git clone <url-do-repositorio> personal-harness
python personal-harness/scripts/install.py --target /caminho/do/projeto
```

No Windows:

```powershell
python personal-harness\scripts\install.py --target C:\caminho\do\projeto
```

O instalador faz uma verificacao completa antes de escrever e recusa sobrescrever arquivos existentes. Depois da instalacao, ele executa o bootstrap local por padrao. Use `--no-bootstrap` somente quando quiser fazer essa etapa manualmente.

Tambem e possivel copiar manualmente:

- `.harness/`
- `.planning/`
- `AGENTS.md`
- `CLAUDE.md`

Depois execute no projeto consumidor:

```bash
python .harness/scripts/bootstrap.py
python .harness/scripts/harness.py doctor
```

Nao execute `bootstrap.py` dentro do repositorio fonte do Personal Harness. Ele foi feito para o projeto consumidor e adiciona os arquivos locais do harness ao `.git/info/exclude` desse projeto.

## Primeiro uso

1. Escreva o produto em `.planning/PRD.md` usando `prd-writer`.
2. Configure os comandos reais do projeto em `.harness/sensors/computational/gates.json`.
3. Escolha um prompt em `.harness/prompts/` ou use linguagem natural.
4. Consulte `.harness/README.md` para os comandos internos e perfis.

Exemplo:

```text
Implemente o produto descrito em .planning/PRD.md usando o perfil lean, de forma autonoma e com entrega no GitHub.
```

## Estrutura

```text
.harness/                 mecanismo, skills, workflows e configuracao
.planning/                template local para PRD, specs e planos
scripts/install.py        instalador seguro para projetos consumidores
scripts/repository_check.py auditoria do repositorio e do pacote
AGENTS.md                 indice lido pelos agentes
CLAUDE.md                 ponte para AGENTS.md
```

Os contratos completos das skills de PRD, spec e implementacao foram preservados. O perfil lean carrega referencias menores, enquanto `manual-classic` e `strict` continuam com o comportamento detalhado.

## Desenvolvimento do harness

```bash
python scripts/repository_check.py
python .harness/scripts/self_test.py
python .harness/scripts/harness.py doctor
python .harness/scripts/model_router.py validate
```

O CI executa essas verificacoes em pushes e pull requests. Consulte [docs/PUBLISHING.md](docs/PUBLISHING.md) para o primeiro push e as configuracoes recomendadas no GitHub.

## Seguranca e privacidade

Nunca publique `.harness/runtime/`, documentos reais em `.planning/`, credenciais, logs ou estado de um projeto consumidor. O `.gitignore` deste repositorio cobre artefatos gerados durante o desenvolvimento do harness. Leia [SECURITY.md](SECURITY.md) antes de relatar uma vulnerabilidade.

## Contribuicao

Leia [CONTRIBUTING.md](CONTRIBUTING.md). Mudancas de comportamento devem incluir ou atualizar um caso em `.harness/evals/cases/`.

## Licenca

MIT. Consulte [LICENSE](LICENSE).
