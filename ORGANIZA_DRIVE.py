#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import shutil
import sys
import re
import unicodedata

def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    texto = texto.upper().replace('-', ' ').replace('_', ' ')
    return re.sub(r'\s+', ' ', texto).strip()

# Função para extrair o formato de um nome de pasta
def extrair_formato(nome):
    # Padrão para formatos como 20X141,50cm, 30X60cm, 23,8x150, etc.
    # Primeiro tenta o padrão com "cm" no final
    padrao_cm = re.compile(r'(\d+(?:,\d+)?X\d+(?:,\d+)?CM)', re.IGNORECASE)
    match_cm = padrao_cm.search(nome.replace(' ', ''))
    if match_cm:
        return match_cm.group(1).upper()
    
    # Se não encontrar, tenta o padrão sem "cm" no final (comum em BiancoGres)
    padrao_sem_cm = re.compile(r'(\d+(?:,\d+)?X\d+(?:,\d+)?)', re.IGNORECASE)
    match_sem_cm = padrao_sem_cm.search(nome.replace(' ', ''))
    if match_sem_cm:
        return match_sem_cm.group(1).upper()
    
    return "SEM_FORMATO"  # Valor padrão se não encontrar formato

# Mapeamento de categorias e palavras-chave
CATEGORIAS = {
    'EXTERNO': ['EXTERNO', 'EXT'],
    'POLIDO': ['POLIDO'],
    'ACETINADO': ['ACETINADO'],
    'NATURAL': ['NATURAL'],
    'DECOR': ['DECOR', 'DECORACAO'],
    'VINILICO': ['VINILICO'],
}

# IDEOGRAPHIC FULL STOP para diferenciar final dos nomes Biancogres
FULL_STOP = '。'

if len(sys.argv) > 1:
    RAIZ = sys.argv[1]
else:
    RAIZ = os.path.dirname(os.path.abspath(__file__))

# Definir raízes de saída
ROOT_BIANCOGRES = os.path.join(RAIZ, 'BIANCOGRES')
ROOT_VILLAGRES = os.path.join(RAIZ, 'VILLAGRES')

# Criar estrutura de pastas
for root in (ROOT_BIANCOGRES, ROOT_VILLAGRES):
    os.makedirs(root, exist_ok=True)
    for cat in CATEGORIAS:
        os.makedirs(os.path.join(root, cat), exist_ok=True)

def organizar_itens(raiz):
    print(f"Organizando itens em: {raiz}\n")
    
    # Contadores para estatísticas
    total_pastas = 0
    pastas_organizadas = 0
    pastas_sem_categoria = 0
    formatos_encontrados = set()

    # Listar tudo na raiz
    for nome in os.listdir(raiz):
        caminho = os.path.join(raiz, nome)
        # Ignorar arquivos e pastas de sistema e as raízes BIANCOGRES e VILLAGRES
        if not os.path.isdir(caminho):
            continue
        if nome in ('BIANCOGRES', 'VILLAGRES'):
            continue
            
        total_pastas += 1

        # Determinar destino pela presença do ideographic full stop
        if nome.endswith(FULL_STOP):
            destino_root = ROOT_BIANCOGRES
        else:
            destino_root = ROOT_VILLAGRES

        # Normalizar para detecção de categoria (remover o FULL_STOP antes)
        nome_limpo = nome.rstrip(FULL_STOP)
        nome_norm = normalizar(nome_limpo)

        # Detectar categoria
        categoria_detectada = None
        for cat, palavras in CATEGORIAS.items():
            for p in palavras:
                if p in nome_norm:
                    categoria_detectada = cat
                    break
            if categoria_detectada:
                break

        if not categoria_detectada:
            print(f"[ ] Sem categoria: '{nome}'")
            pastas_sem_categoria += 1
            continue

        # Extrair formato do nome da pasta
        formato = extrair_formato(nome_limpo)
        formatos_encontrados.add(formato)
        
        # Montar caminho de destino com o formato incluído
        destino = os.path.join(destino_root, categoria_detectada, formato, nome)
        
        # Criar pasta de formato se não existir
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        
        if os.path.abspath(caminho) == os.path.abspath(destino):
            print(f"[ ] Já organizado: '{nome}'")
            continue

        # Mover pasta
        try:
            shutil.move(caminho, destino)
            print(f"[✔] Movido: '{nome}' → '{os.path.relpath(destino, raiz)}'")
            pastas_organizadas += 1
        except Exception as e:
            print(f"[✘] Erro ao mover '{nome}': {e}")

    # Exibir estatísticas
    print("\n=== Estatísticas ===")
    print(f"Total de pastas processadas: {total_pastas}")
    print(f"Pastas organizadas: {pastas_organizadas}")
    print(f"Pastas sem categoria: {pastas_sem_categoria}")
    print(f"Formatos encontrados: {len(formatos_encontrados)}")
    for fmt in sorted(formatos_encontrados):
        print(f"  - {fmt}")
    
    print("\nOrganização concluída com sucesso!")

if __name__ == '__main__':
    organizar_itens(RAIZ)