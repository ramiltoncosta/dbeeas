# Arquitetura e decisões do DBeeAS

Registro das decisões tomadas, para consulta futura.

## Visão geral

```
                    Internet
                       │
                   [Traefik]  ← único que expõe portas (80/443), HTTPS automático
              ┌────────┴─────────┐
     dbeeas.com.br        api.dbeeas.com.br
              │                  │
        [frontend]          [backend]  ← FastAPI: login, coletas, mapa, exportação
     React (nginx)             │   │
                               │   └──► [Redis] ◄── [worker]   (etapa 2)
                               │                        │
                          [PostgreSQL + PostGIS] ◄──────┤
                               │                        ▼
                         [armazenamento]          [detector]  ← API YOLO (/detect)
                          (fotos, ZIPs)            só na rede interna
```

## Decisões

| Data | Decisão | Motivo |
|---|---|---|
| 2026-10-23 | O detector deixa de ser público; o usuário identifica fotos pelo backend | Controle de login e de limite do plano |
| 2026-10-23 | O worker chama o detector em vez de carregar o modelo de novo | Uma só cópia do YOLOv8x na memória |
| 2026-10-23 | RQ em vez de Celery | Mais simples de entender e manter |
| 2026-10-23 | Localização exata de espécies sensíveis: dono da foto, administrador e pesquisadores | Definido pelo responsável do projeto. Opção `PESQUISADOR_REQUER_APROVACAO` permite exigir aprovação do administrador |
| 2026-10-23 | E-mails: simulador (Mailpit) no desenvolvimento; em produção, só no log até haver um serviço de e-mail | Ainda não há serviço de e-mail contratado |
| 2026-10-23 | Sessão: token de acesso de 15 min na memória do navegador + refresh token num cookie protegido (httpOnly). O aplicativo recebe o refresh token no corpo da resposta (cabeçalho `X-Cliente: app`) | Evita que um script malicioso na página roube a sessão |
| 2026-10-23 | Refresh token trocado a cada uso; se um token antigo reaparecer, todas as sessões da conta são encerradas | Detecta roubo de sessão |

## Modelo de dados

Etapa 1 (implementado): `usuarios`, `tokens`.

Próximas etapas: `planos`, `assinaturas`, `modelos`, `especies`, `coletas`, `fotos`,
`identificacoes`, `revisoes`, `exportacoes`.

Campos extras da coleta (definidos para a etapa 2): tipo de armadilha, isca atrativa,
bioma e sexo do espécime (por foto).

## Perfis

| Perfil | Quem escolhe | Observação |
|---|---|---|
| Pesquisador | Cadastro | Vê localização exata de espécies sensíveis |
| Órgão público | Cadastro | |
| Estudante | Cadastro | |
| Administrador | Só pelo comando `criar-admin` ou por outro administrador | |
