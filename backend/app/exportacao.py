"""Exportação da coleta: ZIP com as fotos separadas por espécie e planilha Darwin Core.

Estrutura do ZIP:

    <nome-da-coleta>/
        LEIA-ME.txt
        ocorrencias.csv                 uma linha por foto (padrão Darwin Core)
        Euglossa_cognata/               uma pasta por espécie (espécie final)
            001_foto-original.jpg
        nao_identificadas/              fotos processadas sem espécie
        nao_processadas/                fotos com erro ou ainda na fila (se houver)

Executado pelo worker (fila "exportacoes").
"""

import csv
import io
import logging
import re
import unicodedata
import uuid
import zipfile
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.armazenamento import get_armazenamento
from app.config import get_settings
from app.db import SessionLocal
from app.emails import enviar_email
from app.geo import lat_lon
from app.models import (
    AcaoRevisao,
    Coleta,
    Exportacao,
    Foto,
    Identificacao,
    OrigemLocal,
    Revisao,
    StatusExportacao,
    StatusFoto,
    TipoImagemExportacao,
    Usuario,
)
from app.security import agora

log = logging.getLogger("dbeeas.exportacao")

NOMES_UF = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}  # fmt: skip

NOMES_BIOMA = {
    "amazonia": "Amazônia", "caatinga": "Caatinga", "cerrado": "Cerrado",
    "mata_atlantica": "Mata Atlântica", "pampa": "Pampa", "pantanal": "Pantanal",
}  # fmt: skip

SEXO_DWC = {"femea": "female", "macho": "male", "indeterminado": "undetermined"}

# Colunas do CSV: termos Darwin Core (https://dwc.tdwg.org/terms/) e, no fim,
# colunas próprias do DBeeAS (prefixo "dbeeas_")
COLUNAS = [
    "occurrenceID", "basisOfRecord", "eventID", "eventDate", "year", "month", "day",
    "scientificName", "genus", "specificEpithet", "taxonRank", "kingdom", "phylum", "class",
    "order", "sex", "individualCount",
    "decimalLatitude", "decimalLongitude", "geodeticDatum", "georeferenceRemarks",
    "country", "countryCode", "stateProvince", "municipality", "habitat", "samplingProtocol",
    "recordedBy", "identifiedBy", "dateIdentified", "identificationVerificationStatus",
    "identificationRemarks", "associatedMedia", "occurrenceRemarks",
    "dbeeas_pasta", "dbeeas_arquivo_original", "dbeeas_status", "dbeeas_especie_modelo",
    "dbeeas_confianca_modelo", "dbeeas_versao_modelo", "dbeeas_revisao", "dbeeas_coleta",
    "dbeeas_tipo_armadilha", "dbeeas_isca_atrativa",
]  # fmt: skip


def nome_seguro(texto: str, padrao: str = "arquivo") -> str:
    """Nome de arquivo/pasta sem acentos nem caracteres problemáticos."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("._")
    return texto[:80] or padrao


def _taxonomia(nome: str | None) -> dict:
    if not nome:
        return {"genus": "", "specificEpithet": "", "taxonRank": ""}
    partes = re.sub(r"\(.*?\)", "", nome).split()
    genero = partes[0] if partes else ""
    especie = next((p for p in partes[1:] if p not in ("aff.", "cf.")), "")
    if especie == "sp.":
        return {"genus": genero, "specificEpithet": "", "taxonRank": "genus"}
    return {"genus": genero, "specificEpithet": especie, "taxonRank": "species"}


def linha_csv(foto: Foto, coleta: Coleta, pasta: str, arquivo_zip: str) -> dict:
    ident: Identificacao | None = foto.identificacao
    rev: Revisao | None = foto.revisao if foto.revisada else None
    especie = foto.especie.nome_cientifico if foto.especie else ""

    lat, lon = lat_lon(foto.local)
    if lat is not None:
        georef = "GPS da foto" if foto.origem_local == OrigemLocal.exif else "Marcado no mapa"
    else:
        lat, lon = lat_lon(coleta.local)
        georef = "Ponto geral da coleta" if lat is not None else ""

    data = foto.data_captura.date() if foto.data_captura else coleta.data_coleta
    versao = ident.modelo.versao if ident and ident.modelo else ""

    if rev:
        identificado_por = rev.usuario.nome if rev.usuario else "Pesquisador(a) (conta removida)"
        data_ident = rev.criado_em.date().isoformat()
        verificacao = "verified by person"
        if rev.acao == AcaoRevisao.confirmou:
            revisao = "confirmada"
        elif rev.acao == AcaoRevisao.corrigiu:
            revisao = "corrigida"
        else:
            revisao = "não identificável"
    elif ident:
        identificado_por = f"DBeeAS (modelo de IA {versao})".replace(" )", ")")
        data_ident = ident.criado_em.date().isoformat()
        verificacao = "not verified (automated identification)"
        revisao = ""
    else:
        identificado_por = data_ident = verificacao = revisao = ""

    observacoes_ident = []
    if ident and ident.confianca is not None:
        observacoes_ident.append(f"Confiança do modelo: {ident.confianca:.2%}")
    if rev and rev.observacao:
        observacoes_ident.append(f"Revisão: {rev.observacao}")

    protocolo = "; ".join(
        x
        for x in (
            f"Armadilha: {coleta.tipo_armadilha}" if coleta.tipo_armadilha else "",
            f"Isca: {coleta.isca_atrativa}" if coleta.isca_atrativa else "",
        )
        if x
    )

    return {
        "occurrenceID": f"urn:dbeeas:foto:{foto.id}",
        "basisOfRecord": "HumanObservation" if rev else "MachineObservation",
        "eventID": f"urn:dbeeas:coleta:{coleta.id}",
        "eventDate": data.isoformat() if data else "",
        "year": data.year if data else "",
        "month": data.month if data else "",
        "day": data.day if data else "",
        "scientificName": especie,
        **_taxonomia(especie),
        "kingdom": "Animalia",
        "phylum": "Arthropoda",
        "class": "Insecta",
        "order": "Hymenoptera",
        "sex": SEXO_DWC.get(foto.sexo.value, "") if foto.sexo else "",
        "individualCount": 1,
        "decimalLatitude": f"{lat:.6f}" if lat is not None else "",
        "decimalLongitude": f"{lon:.6f}" if lon is not None else "",
        "geodeticDatum": "WGS84" if lat is not None else "",
        "georeferenceRemarks": georef,
        "country": "Brasil",
        "countryCode": "BR",
        "stateProvince": NOMES_UF.get(coleta.uf or "", ""),
        "municipality": coleta.municipio or "",
        "habitat": NOMES_BIOMA.get(coleta.bioma.value, "") if coleta.bioma else "",
        "samplingProtocol": protocolo,
        "recordedBy": coleta.coletor or "",
        "identifiedBy": identificado_por,
        "dateIdentified": data_ident,
        "identificationVerificationStatus": verificacao,
        "identificationRemarks": " | ".join(observacoes_ident),
        "associatedMedia": arquivo_zip,
        "occurrenceRemarks": coleta.observacoes or "",
        "dbeeas_pasta": pasta,
        "dbeeas_arquivo_original": foto.nome_original,
        "dbeeas_status": foto.status.value,
        "dbeeas_especie_modelo": ident.especie.nome_cientifico if ident and ident.especie else "",
        "dbeeas_confianca_modelo": f"{ident.confianca:.4f}"
        if ident and ident.confianca is not None
        else "",
        "dbeeas_versao_modelo": versao,
        "dbeeas_revisao": revisao,
        "dbeeas_coleta": coleta.nome,
        "dbeeas_tipo_armadilha": coleta.tipo_armadilha or "",
        "dbeeas_isca_atrativa": coleta.isca_atrativa or "",
    }


def _pasta_da_foto(foto: Foto) -> str:
    if foto.status != StatusFoto.concluida:
        return "nao_processadas"
    if foto.especie:
        return nome_seguro(foto.especie.nome_cientifico, "especie")
    return "nao_identificadas"


def _leia_me(coleta: Coleta, fotos: list[Foto], pastas: dict[str, int], tipo: str) -> str:
    versoes = sorted(
        {f.identificacao.modelo.versao for f in fotos if f.identificacao and f.identificacao.modelo}
    )
    linhas_pastas = "\n".join(f"  {p}/  ({n} foto(s))" for p, n in sorted(pastas.items()))
    campos = [
        ("Coleta", coleta.nome),
        ("Data da coleta", coleta.data_coleta.strftime("%d/%m/%Y") if coleta.data_coleta else ""),
        ("Município/UF", " / ".join(x for x in (coleta.municipio, coleta.uf) if x)),
        ("Bioma", NOMES_BIOMA.get(coleta.bioma.value, "") if coleta.bioma else ""),
        ("Coletor(a)", coleta.coletor),
        ("Tipo de armadilha", coleta.tipo_armadilha),
        ("Isca atrativa", coleta.isca_atrativa),
    ]
    dados = "\n".join(f"{k}: {v}" for k, v in campos if v)
    return f"""DBeeAS – Sistema inteligente de reconhecimento de abelhas pela asa
Amostra digital exportada em {agora().strftime("%d/%m/%Y %H:%M")} (UTC)

{dados}
Total de fotos: {len(fotos)}
Imagens: {"originais, sem alteração" if tipo == "original" else "reduzidas (até 1600 px)"}
Versão(ões) do modelo de identificação: {", ".join(versoes) or "-"}

PASTAS
{linhas_pastas}

Cada foto fica na pasta da sua espécie FINAL: a confirmada ou corrigida por uma
pessoa, quando houver revisão; senão, a indicada pelo modelo. As fotos que o modelo
não conseguiu identificar com segurança ficam em "nao_identificadas".

PLANILHA ocorrencias.csv
Uma linha por foto, com colunas no padrão Darwin Core (https://dwc.tdwg.org/terms/),
compatível com SiBBr e GBIF, mais colunas próprias do DBeeAS (começam com "dbeeas_").
- basisOfRecord: MachineObservation = identificação só pelo modelo;
  HumanObservation = conferida por uma pessoa.
- georeferenceRemarks: de onde veio a coordenada (GPS da foto, marcada no mapa
  ou ponto geral da coleta).
- dbeeas_especie_modelo / dbeeas_confianca_modelo: o que o modelo indicou,
  mesmo quando uma pessoa corrigiu depois.
Arquivo em UTF-8, separado por vírgulas. No Excel, use Dados > Obter dados > De Texto/CSV
e escolha a origem "65001: Unicode (UTF-8)" e o delimitador "Vírgula".

As identificações automáticas podem conter erros e não substituem a análise
de um especialista.
"""


def gerar_zip(db: Session, exportacao: Exportacao, destino: Path) -> int:
    """Escreve o ZIP em `destino`. Retorna o número de fotos."""
    coleta = db.get(Coleta, exportacao.coleta_id)
    fotos = db.scalars(
        select(Foto)
        .where(Foto.coleta_id == coleta.id)
        .options(
            selectinload(Foto.identificacoes).selectinload(Identificacao.especie),
            selectinload(Foto.identificacoes).selectinload(Identificacao.modelo),
            selectinload(Foto.especie),
            selectinload(Foto.revisoes).selectinload(Revisao.usuario),
        )
        .order_by(Foto.enviada_em, Foto.nome_original)
    ).all()

    arm = get_armazenamento()
    raiz = nome_seguro(coleta.nome, "coleta")
    contadores: dict[str, int] = {}
    linhas = []

    # Agrupa por pasta (o ZIP fica organizado); dentro da pasta, ordem de envio
    fotos_por_pasta = sorted(
        ((_pasta_da_foto(f), i, f) for i, f in enumerate(fotos)), key=lambda t: (t[0], t[1])
    )

    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for pasta, _, foto in fotos_por_pasta:
            contadores[pasta] = contadores.get(pasta, 0) + 1
            usar_reduzida = exportacao.tipo_imagem == TipoImagemExportacao.reduzida and foto.media
            chave = foto.media if usar_reduzida else foto.arquivo
            base = nome_seguro(foto.nome_original.rsplit(".", 1)[0], "foto")
            extensao = "jpg" if usar_reduzida else foto.arquivo.rsplit(".", 1)[-1]
            # Número na frente: evita dois arquivos com o mesmo nome na mesma pasta
            nome = f"{contadores[pasta]:03d}_{base}.{extensao}"
            caminho_zip = f"{pasta}/{nome}"
            try:
                # Fotos já são comprimidas (JPEG): guardar sem comprimir de novo é mais rápido
                z.write(arm.caminho(chave), f"{raiz}/{caminho_zip}")
            except (FileNotFoundError, ValueError):
                log.warning("Arquivo da foto %s não encontrado; fica só na planilha", foto.id)
                caminho_zip = ""
            linhas.append(linha_csv(foto, coleta, pasta, caminho_zip))

        texto = io.StringIO()
        escritor = csv.DictWriter(texto, fieldnames=COLUNAS, lineterminator="\r\n")
        escritor.writeheader()
        escritor.writerows(linhas)
        # BOM no início: o Excel reconhece os acentos
        z.writestr(
            f"{raiz}/ocorrencias.csv",
            "﻿" + texto.getvalue(),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        z.writestr(
            f"{raiz}/LEIA-ME.txt",
            _leia_me(coleta, fotos, contadores, exportacao.tipo_imagem.value),
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return len(fotos)


def gerar_exportacao(exportacao_id: str) -> str:
    """Tarefa da fila. Retorna o status final."""
    s = get_settings()
    arm = get_armazenamento()
    with SessionLocal() as db:
        exp = db.get(Exportacao, uuid.UUID(exportacao_id))
        if exp is None:
            return "removida"
        exp.status = StatusExportacao.gerando
        db.commit()

        coleta = db.get(Coleta, exp.coleta_id)
        nome_zip = f"DBeeAS_{nome_seguro(coleta.nome, 'coleta')}_{agora():%Y-%m-%d}.zip"
        chave = f"exportacoes/{exp.usuario_id}/{exp.id}/{nome_zip}"
        temporario = arm.pasta_temporaria() / f"{exp.id}.zip"
        try:
            exp.total_fotos = gerar_zip(db, exp, temporario)
            exp.tamanho_bytes = temporario.stat().st_size
            arm.mover_para(chave, temporario)
            exp.arquivo = chave
            exp.status = StatusExportacao.pronta
            exp.concluida_em = agora()
            exp.expira_em = agora() + timedelta(days=s.exportacao_dias)
            db.commit()
        except Exception as e:
            db.rollback()
            temporario.unlink(missing_ok=True)
            log.exception("Falha ao gerar a exportação %s", exportacao_id)
            exp.status = StatusExportacao.erro
            exp.erro = "Não foi possível gerar o arquivo. Tente de novo."
            db.commit()
            return f"erro: {e.__class__.__name__}"

        usuario = db.get(Usuario, exp.usuario_id)
        if usuario:
            enviar_email(
                usuario.email,
                f"DBeeAS – Exportação pronta: {coleta.nome}",
                f"Olá, {usuario.nome}.\n\n"
                f'O arquivo da coleta "{coleta.nome}" está pronto para baixar '
                f"({exp.total_fotos} foto(s)).\n\n"
                f"Acesse: {s.frontend_url.rstrip('/')}/coletas/{coleta.id}\n\n"
                f"O arquivo fica disponível por {s.exportacao_dias} dias.\n\nEquipe DBeeAS",
            )
        return exp.status.value


def apagar_expiradas(db: Session) -> int:
    """Apaga os ZIPs vencidos (o registro fica, com status "expirada" calculado)."""
    arm = get_armazenamento()
    vencidas = db.scalars(
        select(Exportacao).where(Exportacao.expira_em < agora(), Exportacao.arquivo.is_not(None))
    ).all()
    for exp in vencidas:
        arm.apagar(exp.arquivo)
        exp.arquivo = None
    db.commit()
    return len(vencidas)
