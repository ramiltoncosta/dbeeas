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
| 2026-10-23 | Fotos guardadas num volume do Docker, atrás de uma interface de armazenamento | Trocar depois por um armazenamento de objetos (S3, R2, B2) sem mudar o resto |
| 2026-10-23 | Imagens entregues por links assinados com prazo (2 h) | `<img>` não envia o token de login; o link só funciona para quem o recebeu da API |
| 2026-10-23 | A foto original é guardada sem alteração; o detector recebe a foto já girada conforme o EXIF | As caixas ficam na mesma posição da imagem mostrada no site |
| 2026-10-23 | Data da foto: fuso gravado pelo aparelho; se não houver, America/Sao_Paulo | O EXIF antigo não guarda fuso |
| 2026-10-23 | Fotos sem GPS herdam o ponto da coleta (não é copiado para a foto) | Corrigir o ponto da coleta corrige todas as fotos sem GPS |
| 2026-10-23 | Fotos repetidas (mesmo conteúdo) na mesma coleta são recusadas | Evita contagens infladas no gráfico |
| 2026-10-23 | O detector informa a versão do modelo (MODEL_VERSION ou hash do arquivo) | Cada identificação registra qual modelo foi usado |
| 2026-10-23 | Espécie final guardada na própria foto (`fotos.especie_id`), recalculada a cada identificação ou revisão | Gráfico, filtros, mapa e exportação ficam rápidos e simples |
| 2026-10-23 | Revisões nunca são apagadas; "desfazer" é uma nova revisão do tipo "restaurou" | Histórico completo e dados confiáveis para retreino |
| 2026-10-23 | Cada revisão guarda o perfil de quem revisou e o que o modelo dizia naquele momento | No retreino dá para usar só correções de pesquisadores |
| 2026-10-23 | Reprocessar uma foto com um modelo novo não desfaz a revisão de uma pessoa | A revisão humana vale mais que o modelo |
| 2026-10-23 | Na correção, o pesquisador pode informar uma espécie que o modelo não conhece (nome científico validado) | Registra espécies novas e gera dados para ampliar o modelo |
| 2026-10-23 | Porcentagens do gráfico calculadas só sobre as fotos identificadas | Não identificadas não distorcem a proporção entre espécies |
| 2026-10-23 | Mapa com dois modos: "Minhas coletas" e "Toda a plataforma" | O valor para pesquisa e governo está em ver a distribuição de todas as ocorrências |
| 2026-10-23 | No modo "Toda a plataforma", ocorrências de outras pessoas aparecem sem foto, sem nome da coleta e sem quem coletou | Protege os dados de quem coletou |
| 2026-10-23 | Cada coleta pode sair do mapa geral (`publica_no_mapa`); o padrão é aparecer | Locais sigilosos, como propriedades particulares |
| 2026-10-23 | Localização aproximada: ponto trocado pelo centro de uma célula fixa do tamanho do raio da espécie | Ruído aleatório pode ser "desfeito" consultando várias vezes; a célula fixa não |
| 2026-10-23 | No mapa, até 3 espécies com cor própria; as demais em cinza ("outras") | Mais de 3 cores em pontos espalhados não se distinguem bem, sobretudo com daltonismo |
| 2026-10-23 | ZIP da exportação gerado no worker (fila `exportacoes`), com aviso por e-mail e link assinado | Coletas grandes levariam minutos; a tela não fica travada esperando |
| 2026-10-23 | Fotos guardadas no ZIP sem nova compressão; só o CSV e o LEIA-ME são comprimidos | JPEG já é comprimido: comprimir de novo gasta processador e não reduz o tamanho |
| 2026-10-23 | Uma pasta por espécie final; `nao_identificadas` e `nao_processadas` à parte; número na frente do nome do arquivo | Duas fotos com o mesmo nome não se sobrescrevem |
| 2026-10-23 | CSV com termos Darwin Core + colunas `dbeeas_*`; UTF-8 com BOM, separado por vírgula | Padrão aceito por SiBBr/GBIF; o BOM faz o Excel mostrar os acentos |
| 2026-10-23 | `basisOfRecord`: MachineObservation (só o modelo) ou HumanObservation (conferida por pessoa) | Quem usa os dados sabe o que foi verificado |
| 2026-10-23 | ZIP fica 7 dias; um novo do mesmo tipo substitui o anterior | Economiza espaço no servidor |
| 2026-10-23 | Refresh token trocado a cada uso; se um token antigo reaparecer, todas as sessões da conta são encerradas | Detecta roubo de sessão |

## Modelo de dados

Etapa 1: `usuarios`, `tokens`.
Etapa 2: `especies`, `modelos`, `coletas`, `fotos`, `identificacoes`.
Etapa 3: `revisoes`; em `fotos`: `especie_id`, `origem_especie`, `revisada`.
Etapa 4: em `coletas`: `publica_no_mapa`.
Etapa 5: `exportacoes`.

Próximas etapas: `planos`, `assinaturas`.

Campos extras: tipo de armadilha, isca atrativa e bioma (na coleta) e sexo do espécime
(na foto).

## Perfis

| Perfil | Quem escolhe | Observação |
|---|---|---|
| Pesquisador | Cadastro | Vê localização exata de espécies sensíveis |
| Órgão público | Cadastro | |
| Estudante | Cadastro | |
| Administrador | Só pelo comando `criar-admin` ou por outro administrador | |
