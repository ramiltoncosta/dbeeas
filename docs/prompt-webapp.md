# Prompt – Aplicação web do DBeeAS

## Contexto

Você vai desenvolver a aplicação web do **DBeeAS – Sistema inteligente de reconhecimento de abelhas pela asa**, um projeto aprovado no programa Centelha e desenvolvido pela startup RCGJ Sistemas Inteligentes.

O sistema identifica a espécie de abelhas a partir de fotos da asa, usando um modelo **YOLOv8x de detecção** (desenha caixas na imagem). O modelo atual reconhece 5 espécies:

- Euglossa pleosticta
- Euglossa modestior
- Euglossa melanotricha
- Euglossa intersecta
- Euglossa cognata

A lista de espécies **não deve ficar fixa no código**: ela vem do endpoint `/health` da API, porque novos modelos vão reconhecer mais espécies.

**Público-alvo:**
- **Pesquisadores**: identificar espécimes, organizar amostras e exportar dados.
- **Órgãos públicos**: monitorar populações e distribuição geográfica para decisões ambientais.
- **Estudantes**: identificar espécies e aprender sobre elas.

**Modelo de negócio:** serviço por assinatura (SaaS). No futuro, haverá uma loja de produtos apícolas, então a arquitetura deve permitir adicionar módulos depois.

Toda a interface deve estar em **português do Brasil**.

## O que já existe

Já existe uma **API de detecção em FastAPI**, rodando em Docker, no repositório `dbeeas`:

```
dbeeas/
├── api/
│   ├── app/main.py        # API de detecção
│   ├── Dockerfile
│   └── requirements.txt
├── models/best.pt         # modelo (fora do Git)
├── docker-compose.yml     # desenvolvimento local
└── docker-compose.prod.yml # produção, com Traefik e HTTPS
```

### Endpoints atuais

**GET /health**

```json
{
  "status": "ok",
  "modelo_carregado": true,
  "especies": ["Euglossa pleosticta", "Euglossa modestior", "..."]
}
```

**POST /detect** (multipart, campo `file`; parâmetro opcional `?annotate=true`)

```json
{
  "identificada": true,
  "especie": "Euglossa cognata",
  "confianca": 0.9312,
  "mensagem": null,
  "deteccoes": [
    {
      "especie": "Euglossa cognata",
      "classe_id": 4,
      "confianca": 0.9312,
      "caixa": {"x1": 120.5, "y1": 88.0, "x2": 940.2, "y2": 610.7}
    }
  ],
  "imagem": {"largura": 1280, "altura": 720},
  "imagem_anotada": "<base64 JPEG, só quando annotate=true>"
}
```

Quando a confiança fica abaixo do limite (`MIN_CONFIDENCE`, padrão 0.50), a resposta vem com `"identificada": false`, `"especie": null` e uma mensagem pedindo outra foto.

Mantenha esse endpoint funcionando. Ele deve ser reaproveitado internamente pelo processamento das fotos, não reescrito.

## Ambiente

- **Desenvolvimento:** Fedora Linux, com Docker e Docker Compose.
- **Produção:** VPS Hostinger em São Paulo (Ubuntu 24.04, 4 vCPU, 16 GB de RAM, **sem GPU**), Docker Compose e Traefik com HTTPS automático (Let's Encrypt).
- **Domínios:** `dbeeas.com.br` (site) e `api.dbeeas.com.br` (API).
- O modelo roda **em CPU**: cada foto pode levar alguns segundos. Nada pode processar imagens dentro da requisição HTTP quando houver mais de uma foto.

## Stack desejada

- **Backend:** FastAPI (Python 3.12), SQLAlchemy 2 + Alembic para migrações, Pydantic para validação.
- **Banco de dados:** PostgreSQL 16 com **PostGIS** (para consultas geográficas).
- **Fila de processamento:** Redis + RQ (ou Celery), com um **worker** separado que roda o modelo.
- **Armazenamento de imagens:** começar com um volume local, mas atrás de uma interface compatível com S3, para migrar depois para um object storage sem mudar o resto do código.
- **Frontend:** React + Vite + TypeScript, Tailwind CSS, React Router, TanStack Query.
- **Mapa:** Leaflet com OpenStreetMap.
- **Gráficos:** Recharts (ou Chart.js).
- **Autenticação:** e-mail e senha, com senhas em hash (argon2 ou bcrypt) e tokens JWT (acesso de curta duração + refresh).
- Tudo em contêineres, com `docker-compose.yml` (desenvolvimento) e `docker-compose.prod.yml` (produção) atualizados. Em produção, **somente o Traefik expõe portas**; banco, Redis e worker ficam apenas na rede interna.

Se discordar de alguma escolha, explique o motivo antes de trocar.

## Funcionalidades do MVP

### 1. Contas e perfis

- Cadastro, login, logout, recuperação de senha por e-mail.
- Perfis: **pesquisador**, **órgão público**, **estudante** e **administrador**.
- Cada usuário só vê e exporta os próprios dados, exceto o administrador.

### 2. Coletas (amostras)

O usuário organiza as fotos em **coletas**. Cada coleta tem:
- nome, descrição, data da coleta, local (município/UF) e coletor;
- várias fotos de espécimes diferentes.

### 3. Envio de fotos em lote

- Envio de várias fotos de uma vez (arrastar e soltar), com barra de progresso do upload.
- Aceitar JPEG, PNG e WEBP, com limite de tamanho por arquivo.
- Ler a localização (latitude/longitude) e a data dos **metadados EXIF** de cada foto, quando existirem.
- Quando não houver localização, permitir marcar o ponto no mapa (para a coleta inteira ou para cada foto).
- Após o upload, as fotos entram na **fila** e são processadas pelo worker. A interface mostra o andamento (ex.: "38 de 120 processadas") e se atualiza sozinha.
- Guardar para cada foto: espécie, confiança, todas as detecções (caixas), localização, data, usuário e coleta.
- Fotos com confiança abaixo do limite ficam como **"não identificadas"**.

### 4. Resultado da coleta

- **Agrupamento por espécie**: fotos organizadas em grupos, com miniaturas.
- **Gráfico** com a porcentagem e a quantidade de cada espécie na coleta. As fotos "não identificadas" aparecem separadas, sem distorcer as porcentagens das espécies.
- Ver cada foto com as **caixas desenhadas** e a confiança.
- **Correção manual**: o pesquisador pode confirmar ou corrigir a espécie de uma foto. Guardar a predição original do modelo e a correção separadamente (esses dados serão usados para retreinar o modelo).

### 5. Mapa

- Mapa com os pontos onde cada espécie foi encontrada, com filtros por espécie, período e coleta.
- Agrupar pontos próximos (clustering) quando houver muitos.
- Clicar num ponto mostra a foto, a espécie, a data e a coleta.
- **Proteção de localização**: permitir marcar uma espécie como sensível; nesse caso, usuários sem permissão veem só uma área aproximada, não o ponto exato.

### 6. Exportação (amostra digital)

- Baixar um **arquivo ZIP** da coleta com:
  - uma pasta por espécie, com as fotos correspondentes;
  - uma pasta `nao_identificadas`;
  - um arquivo **CSV** com uma linha por foto, seguindo os termos do padrão **Darwin Core** sempre que possível (ex.: `occurrenceID`, `scientificName`, `eventDate`, `decimalLatitude`, `decimalLongitude`, `municipality`, `stateProvince`, `country`, `recordedBy`, `identifiedBy`, `identificationRemarks`), mais colunas próprias para a confiança do modelo e a versão do modelo usada.
- A geração do ZIP também deve rodar no worker, com aviso quando estiver pronto para baixar.

### 7. Painel

- Página inicial do usuário com resumo: total de coletas, fotos, espécies encontradas e últimas coletas.

### 8. Fichas das espécies (base para estudantes)

- Uma página por espécie com nome científico, descrição, características, distribuição e fontes.
- O conteúdo deve ser editável pelo administrador (não fixo no código), porque será escrito e revisado por especialistas.

### 9. Página pública

- Página inicial em `dbeeas.com.br` apresentando o projeto, como funciona, para quem é, planos e contato.
- Mencionar o apoio do programa Centelha e a empresa RCGJ Sistemas Inteligentes no rodapé.

## Assinaturas

- Modelar desde já **planos** (ex.: estudante, pesquisador, institucional) com limites, como número de fotos por mês.
- O sistema deve **bloquear o envio** quando o limite do plano for atingido ou a assinatura não estiver ativa.
- A cobrança recorrente será integrada depois com um gateway brasileiro (Asaas, Mercado Pago ou Pagar.me). Por enquanto, crie uma **interface de pagamento abstrata** e permita que o administrador ative e altere planos manualmente.

## Requisitos não funcionais

- **Segurança:** validação de todos os uploads (tipo real do arquivo, não só a extensão), limite de requisições por usuário, CORS restrito aos domínios do projeto, segredos em variáveis de ambiente (`.env`), nunca no código.
- **LGPD:** página de termos de uso e política de privacidade, consentimento explícito no cadastro (incluindo o uso das fotos para melhorar o modelo), opção de o usuário exportar e excluir seus dados.
- **Responsivo:** a interface precisa funcionar bem no celular, porque muitos usuários vão acessar em campo.
- **Versão do modelo:** registrar em cada identificação qual versão do modelo foi usada.
- **Backups:** incluir um script de backup do PostgreSQL e das imagens.
- **Testes:** testes automatizados para os pontos principais do backend (autenticação, upload, processamento, exportação).
- **Documentação:** atualizar o README com instruções para rodar localmente e em produção. A API deve ser pensada para ser usada também por um **aplicativo de celular** que será desenvolvido depois, então os endpoints devem ser documentados no `/docs` do FastAPI.

## Fora do escopo agora

Não implementar neste momento (mas não impedir na arquitetura):
- aplicativo de celular;
- modo offline;
- painel institucional avançado para órgãos públicos;
- loja de produtos apícolas;
- integração real com gateway de pagamento.

## Como trabalhar

1. Antes de escrever código, apresente a **arquitetura**, o **modelo de dados** (tabelas e relações) e a **lista de endpoints**, e espere minha aprovação.
2. Desenvolva **em etapas**, nesta ordem, e pare ao final de cada uma para eu testar:
   1. Banco de dados, autenticação e perfis.
   2. Coletas e envio de fotos com a fila de processamento.
   3. Resultado da coleta: agrupamento, gráfico e correção manual.
   4. Mapa.
   5. Exportação ZIP com CSV Darwin Core.
   6. Painel, fichas das espécies e página pública.
   7. Planos e limites de uso.
3. Em cada etapa, diga quais comandos eu devo rodar para testar e o que devo ver.
4. Explique as decisões técnicas de forma simples. Sou pesquisador e estou aprendendo a parte de infraestrutura.
5. Use **commits pequenos**, com mensagens em português.
