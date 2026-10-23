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

**Backup:** o banco (volume `dbdata`) e as fotos (volume `arquivos`) são os dados do
projeto. O script de backup entra numa próxima etapa; até lá, não apague esses volumes.

### DNS (Registro.br)

| Tipo | Nome | Valor |
|---|---|---|
| A | (vazio) | IP do servidor |
| A | www | IP do servidor |
| A | api | IP do servidor |

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
- [ ] Etapa 5 – Exportação ZIP com CSV Darwin Core
- [ ] Etapa 6 – Painel, fichas das espécies e página pública
- [ ] Etapa 7 – Planos e limites de uso
