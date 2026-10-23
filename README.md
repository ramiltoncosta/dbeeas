# DBeeAS

Sistema inteligente de reconhecimento de abelhas pela asa.
RCGJ Sistemas Inteligentes – CNPJ 66.904.746/0001-38 · Projeto apoiado pelo Programa Centelha.

## Estrutura

```
dbeeas/
├── api/                    # detector: API do modelo YOLO (uso interno)
├── backend/                # API principal: contas, coletas, mapa, exportação
│   ├── app/                #   código (FastAPI)
│   ├── alembic/            #   migrações do banco de dados
│   └── tests/              #   testes automatizados
├── frontend/               # site (React)
├── models/                 # coloque aqui o best.pt (não vai para o Git)
├── scripts/                # backup e restauração (servidor)
├── docs/                   # documentação e prompt do projeto
├── docker-compose.yml      # desenvolvimento
└── docker-compose.prod.yml # produção
```

Como as partes se conectam:

```
navegador ──► frontend (React)
          └─► backend (FastAPI) ──► PostgreSQL + PostGIS
                     │
                     └─► Redis (fila) ◄── worker ──► detector (YOLO)
```

## Desenvolvimento (no seu computador)

Pré-requisito: Docker instalado (veja abaixo).

1. Copie o modelo para `models/best.pt`.
2. Na pasta do projeto:

   ```bash
   docker compose up --build
   ```

   A primeira vez demora alguns minutos.

3. Abra:

   | O quê | Endereço |
   |---|---|
   | Site | http://localhost:5173 |
   | Documentação da API | http://localhost:8000/docs |
   | E-mails de teste (ex.: recuperação de senha) | http://localhost:8025 |
   | Detector direto | http://localhost:8001/docs |

4. Crie o primeiro administrador (em outro terminal, com o sistema rodando):

   ```bash
   docker compose exec backend python -m app.cli criar-admin
   ```

5. Para ver as fotos sendo processadas:

   ```bash
   docker compose logs -f worker
   ```

### Testes

```bash
docker compose exec backend pytest
```

### Parar

`Ctrl+C` no terminal, ou `docker compose down`. Para apagar também o banco de dados
de desenvolvimento: `docker compose down -v`.

### Instalar o Docker no Fedora

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Saia e entre de novo na sessão para o grupo `docker` valer.

## Produção (servidor)

No servidor, na pasta do projeto:

```bash
cp .env.example .env
nano .env          # preencha senhas e e-mail (instruções dentro do arquivo)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python -m app.cli criar-admin
```

- Site: https://dbeeas.com.br
- API: https://api.dbeeas.com.br (documentação em `/docs`)
- O HTTPS é configurado automaticamente pelo Traefik.
- O detector não é mais acessível pela internet: só o backend fala com ele.

Ver o que está acontecendo:

```bash
docker compose -f docker-compose.prod.yml logs -f backend worker
```

### Backup

O banco (volume `dbdata`) e as fotos (volume `arquivos`) são os dados do projeto.

```bash
./scripts/backup.sh          # cria backups/AAAA-MM-DD_HHMM/ (banco.dump e arquivos.tar.gz)
```

Os backups com mais de 14 dias são apagados sozinhos (`BACKUP_DIAS=30 ./scripts/backup.sh` muda o prazo).
Para rodar todo dia às 3h30, abra o agendador com `crontab -e` e acrescente:

```
30 3 * * * cd /home/ramilton/dbeeas && ./scripts/backup.sh >> backups/backup.log 2>&1
```

**Guarde uma cópia fora do servidor.** Se o servidor tiver problema, um backup que só existe nele
se perde junto. O jeito mais simples é baixar a pasta de vez em quando para o seu computador:

```bash
scp -r ramilton@2.25.96.33:dbeeas/backups/2026-10-23_0330 ~/Backups-DBeeAS/
```

Para restaurar (substitui os dados atuais e pede confirmação):

```bash
./scripts/restaurar.sh backups/2026-10-23_0330
```

### DNS (Registro.br)

| Tipo | Nome | Valor |
|---|---|---|
| A | (vazio) | IP do servidor |
| A | www | IP do servidor |
| A | api | IP do servidor |

## Planos e assinaturas

- Toda conta nova ganha um **teste gratuito** (30 dias, `DIAS_TESTE`) no plano do perfil:
  estudante → Estudante, pesquisador → Pesquisador, órgão público → Institucional.
- O limite conta as fotos enviadas às coletas e as da identificação rápida no mês (fuso de Brasília).
  O saldo renova no dia 1º. Apagar fotos não devolve o saldo. Administradores não têm limite.
- Sem plano válido (teste vencido, suspenso, cancelado) ou sem saldo, o envio é bloqueado com uma
  mensagem que explica o motivo. As coletas, o mapa e a exportação dos dados continuam funcionando.
- **Preços e limites:** Administração › Planos. Plano sem preço aparece como "sob consulta".
- **Ativar o plano de alguém** (depois do pagamento): Administração › Usuários › "Gerenciar plano".
  O filtro "Pedidos de plano" mostra quem pediu um plano pelo site. Cada mudança fica no histórico.
- **Cobrança automática:** ainda não existe. O código tem uma interface de pagamento
  (`backend/app/pagamentos.py`) pronta para receber o Asaas, o Mercado Pago ou o Pagar.me; hoje o modo é
  `GATEWAY_PAGAMENTO=manual`.

## Configurações do backend

Definidas por variáveis de ambiente (veja `.env.example` e `backend/app/config.py`).

| Variável | O que faz |
|---|---|
| `JWT_SECRET` | Segredo dos tokens de login. Obrigatório em produção. |
| `ACCESS_TOKEN_MINUTOS` | Duração do token de acesso (padrão 15) |
| `REFRESH_TOKEN_DIAS` | Por quanto tempo a pessoa fica logada (padrão 30) |
| `SMTP_HOST` e afins | Serviço de e-mail. Vazio = e-mails só no log |
| `UPLOAD_MAX_MB` | Tamanho máximo de cada foto (padrão 15) |
| `MAX_TENTATIVAS` | Quantas vezes o worker tenta processar uma foto (padrão 3) |
| `DIAS_TESTE` | Dias de teste gratuito para contas novas (padrão 30) |
| `GATEWAY_PAGAMENTO` | Serviço de cobrança. Hoje só `manual` (o administrador ativa os planos) |
| `EMAIL_CONTATO` | Para onde vão as mensagens do formulário de contato (padrão contato@dbeeas.com.br). Elas também ficam em Administração > Mensagens |
| `CONFIANCA_REVISAO` | Abaixo desta confiança, fotos sem revisão aparecem como "para conferir" (padrão 0.7) |
| `EXPORTACAO_DIAS` | Por quantos dias o ZIP exportado fica disponível (padrão 7) |
| `FUSO_HORARIO_PADRAO` | Fuso da data das fotos quando o aparelho não grava (padrão America/Sao_Paulo) |
| `PESQUISADOR_REQUER_APROVACAO` | Se `true`, pesquisadores precisam de aprovação do administrador para ver a localização exata de espécies sensíveis |

## Detector (YOLO)

| Variável | Padrão | O que faz |
|---|---|---|
| MODEL_PATH | /models/best.pt | Caminho do modelo |
| MIN_CONFIDENCE | 0.50 | Abaixo disso, responde "não identificada" |
| DETECT_CONFIDENCE | 0.25 | Limiar mínimo do YOLO para considerar uma caixa |
| IMG_SIZE | 640 | Tamanho da imagem usada no modelo |
| MAX_UPLOAD_MB | 15 | Tamanho máximo do arquivo enviado |

## Andamento

Plano completo em [docs/prompt-webapp.md](docs/prompt-webapp.md) e decisões em
[docs/arquitetura.md](docs/arquitetura.md).

- [x] Etapa 1 – Banco de dados, autenticação e perfis
- [x] Etapa 2 – Coletas e envio de fotos com fila de processamento
- [x] Etapa 3 – Resultado da coleta: agrupamento, gráfico e correção manual
- [x] Etapa 4 – Mapa
- [x] Etapa 5 – Exportação ZIP com CSV Darwin Core
- [x] Etapa 6 – Painel, fichas das espécies e página pública
- [x] Etapa 7 – Planos e limites de uso
