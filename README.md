# DBeeAS

Sistema inteligente de reconhecimento de abelhas pela asa.
RCGJ Sistemas Inteligentes – CNPJ 66.904.746/0001-38

## Estrutura

```
dbeeas/
├── api/                 # API de detecção (FastAPI + YOLO)
│   ├── app/main.py
│   ├── Dockerfile
│   └── requirements.txt
├── models/              # coloque aqui o best.pt (não vai para o Git)
└── docker-compose.yml
```

## Instalar o Docker no Fedora

O Fedora vem com o Podman, mas vamos usar o Docker para ficar igual ao servidor:

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Saia e entre de novo na sessão para o grupo `docker` valer.

## Rodar a API

1. Copie o modelo para `models/best.pt`.
2. Na pasta do projeto:

```bash
docker compose up --build
```

A primeira vez demora alguns minutos (baixa o PyTorch).

## Testar

- Documentação interativa: http://localhost:8000/docs
- Saúde da API: `curl http://localhost:8000/health`
- Detecção:

```bash
curl -F "file=@asa.jpg" http://localhost:8000/detect
```

- Com a imagem anotada (caixas desenhadas, em base64):

```bash
curl -F "file=@asa.jpg" "http://localhost:8000/detect?annotate=true"
```

## Configurações (docker-compose.yml)

| Variável | Padrão | O que faz |
|---|---|---|
| MODEL_PATH | /models/best.pt | Caminho do modelo |
| MIN_CONFIDENCE | 0.50 | Abaixo disso, responde "não identificada" |
| DETECT_CONFIDENCE | 0.25 | Limiar mínimo do YOLO para considerar uma caixa |
| IMG_SIZE | 640 | Tamanho da imagem usada no modelo |
| MAX_UPLOAD_MB | 15 | Tamanho máximo do arquivo enviado |
