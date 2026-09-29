"""Moderação automática do conteúdo PÚBLICO dos perfis (Parte 7 do plano).

Regras locais, sem serviço de terceiros: nenhum texto sai do servidor para "IA" de fora. Só olha o
que já é público (nome de exibição e bio), nunca as mensagens privadas.

Filosofia: poucas regras, de alta precisão, para os casos graves. Uma sinalização NÃO bane
ninguém: cria uma denúncia do sistema e, sendo grave, deixa a conta em revisão (oculta) até uma
pessoa da moderação decidir.
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Sinal:
    motivo: str  # mesmo vocabulário das denúncias
    trecho: str  # o pedaço do texto que disparou a regra (para a moderação avaliar)


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


# Idade declarada entre 10 e 17 anos, só em formas típicas de apresentação (primeira pessoa ou o
# número sozinho junto do nome), para não confundir com "3 anos de namoro" ou "moro há 5 anos".
_IDADE = re.compile(
    r"\b(tenho|tenh|to com|tou com|estou com|fiz|faco|vou fazer|idade\s*[:=]?)\s*(1[0-7])\b"
    r"|(?:^|[,|•/-])\s*(1[0-7])\s*(anos|aninhos|a|y/?o|yo)?\s*(?:$|[,|•/!.-])"
    r"|\b(1[0-7])\s*(aninhos|a|y/?o|yo)\b"
)
# "Sou menor", "menor de idade", "de menor", "ensino fundamental/médio" — exceto quando negado.
_MENOR = re.compile(r"\b(sou menor|menor de idade|de menor|ensino (fundamental|medio)|estou no \d?\s*ano do)\b")
_NEGACAO = re.compile(r"\b(nao|nunca|nada de|proibido|sem|zero|jamais)\b[^.!?\n]{0,25}$")


def _negado(texto: str, inicio: int) -> bool:
    return bool(_NEGACAO.search(texto[max(0, inicio - 30) : inicio]))


def analisar(*textos: str | None) -> list[Sinal]:
    """Sinais encontrados no conteúdo público do perfil (vazio = nada a fazer)."""
    sinais = []
    for original in filter(None, textos):
        texto = _sem_acentos(original)
        for regra in (_IDADE, _MENOR):
            for m in regra.finditer(texto):
                # A negação vale até a palavra "menor" ("nada de menor de idade", "não sou menor").
                ancora = texto.find("menor", m.start(), m.end())
                if not _negado(texto, ancora if ancora >= 0 else m.start()):
                    sinais.append(Sinal("menor_de_idade", original[max(0, m.start() - 20) : m.end() + 20].strip()))
    return sinais
