#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import time
import urllib.request
from urllib.parse import urlparse, urljoin
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import sys

# Lista de categorias a baixar
DOWNLOAD_TYPES = ['faces do produto', 'bloco de sketchup', 'paginação', 'ambiente']

# Nome do arquivo de URLs (padrão)
ARQUIVO_URLS = 'biancogres_links.txt'

# Funções auxiliares
def limpar_nome_para_pasta(nome: str) -> str:
    """Remove espaços extras e caracteres inválidos, preservando caso original."""
    texto = nome.replace('\n', ' ')
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'[\\/*?:"<>|]', '', texto)
    return texto.strip()


def extrair_formato(texto: str) -> str:
    """Extrai o formato no padrão NxN ou N,NxN,N do texto."""
    # Padrão para formatos como 20X141,50cm ou 23,8x150
    padrao = re.compile(r'(\d+(?:,\d+)?[Xx]\d+(?:,\d+)?(?:cm)?)', re.IGNORECASE)
    match = padrao.search(texto.replace(' ', ''))
    return match.group(1) if match else ""


def baixar_arquivo(url: str, pasta: str, nome_arquivo: str = None, cookies=None, headers=None) -> None:
    """Baixa arquivo: imagens via urllib, outros via requests."""
    if not nome_arquivo:
        nome_arquivo = os.path.basename(urlparse(url).path)
    caminho = os.path.join(pasta, nome_arquivo)
    ext = os.path.splitext(nome_arquivo)[1].lower()

    # Imagens
    if ext in ['.jpg', '.jpeg', '.png']:
        try:
            os.makedirs(pasta, exist_ok=True)
            urllib.request.urlretrieve(url, caminho)
            print(f"[✔] Imagem baixada: {caminho}")
        except Exception as e:
            print(f"[✘] Erro ao baixar imagem {url}: {e}")
        return

    # Outros arquivos (PDF, ZIP, RAR...)
    sess = requests.Session()
    if cookies:
        for c in cookies:
            sess.cookies.set(c['name'], c['value'])
    hdr = headers or {'User-Agent': 'Mozilla/5.0'}

    for tentativa in range(1, 4):
        try:
            resp = sess.get(url, headers=hdr, stream=True, timeout=30)
            resp.raise_for_status()
            os.makedirs(pasta, exist_ok=True)
            with open(caminho, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            if os.path.getsize(caminho) > 0:
                print(f"[✔] Arquivo baixado: {caminho}")
                return
            else:
                print(f"[✘] Arquivo vazio: {caminho}")
        except Exception as e:
            print(f"[✘] Tentativa {tentativa}/3 falhou: {e}")
            time.sleep(1)
    print(f"[✘] Não foi possível baixar {url} após 3 tentativas.")


def tirar_screenshot_full(driver, caminho: str) -> None:
    """Captura screenshot de página inteira."""
    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
    time.sleep(1)
    w = driver.execute_script('return document.body.scrollWidth')
    h = driver.execute_script('return document.body.scrollHeight')
    driver.set_window_size(w, h)
    driver.save_screenshot(caminho)
    print(f"[✔] Screenshot salvo em: {caminho}")


def baixar_dados(link: str) -> None:
    """Coleta dados, imagens e arquivos técnicos de um produto BiancoGres."""
    servico = Service(ChromeDriverManager().install())
    opts = webdriver.ChromeOptions()
    opts.add_argument('--headless')
    driver = webdriver.Chrome(service=servico, options=opts)
    driver.set_window_size(1920, 1080)

    try:
        driver.get(link)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # === Coleta nome do produto ===
        nome_produto = ""
        
        # Método 1: Tenta extrair do título da página
        titulo = soup.find('h2', class_='product__title')
        if titulo:
            texto_titulo = titulo.get_text(strip=True)
            # Tenta extrair o nome entre parênteses
            m = re.search(r"$$(.*?)$$", texto_titulo)
            if m:
                nome_produto = m.group(1)
            else:
                # Se não tem parênteses, usa o título completo
                nome_produto = texto_titulo
        
        # Método 2: Se não encontrou pelo título, tenta pelo URL
        if not nome_produto:
            # Extrai o nome do produto da URL (geralmente é o último segmento)
            url_path = urlparse(link).path.strip('/').split('/')
            if url_path:
                nome_produto = url_path[-1].replace('-', ' ').title()
        
        # Método 3: Tenta encontrar em elementos específicos da página
        if not nome_produto:
            # Procura em elementos com classes específicas que possam conter o nome
            nome_elementos = soup.select('.product-name, .product-title, h1')
            for elem in nome_elementos:
                if elem.text.strip():
                    nome_produto = elem.text.strip()
                    break
        
        nome_produto = limpar_nome_para_pasta(nome_produto)
        
        # Verifica se o nome do produto foi encontrado
        if not nome_produto:
            nome_produto = "Produto Desconhecido"
            print(f"[⚠] Aviso: Nome do produto não encontrado, usando '{nome_produto}'")
        else:
            print(f"[ℹ] Nome do produto: {nome_produto}")

        # === Coleta acabamento ===
        acabamento = ''
        itens_info = soup.select('section.product__technical__informations__container.active li')
        for item in itens_info:
            span_nome = item.find('span', class_='product__technical__informations__name')
            span_valor = item.find('span', class_='product__technical__informations__value')
            if span_nome and span_valor:
                label = ''.join(t for t in span_nome.find_all(text=True, recursive=False)).strip().lower()
                if label == 'acabamento':
                    acabamento = limpar_nome_para_pasta(span_valor.get_text(strip=True))
                    break
        
        if acabamento:
            print(f"[ℹ] Acabamento: {acabamento}")

        # === Coleta formato (tamanho) ===
        formato = ''
        
        # Procura pelo formato nos botões de tamanho
        formato_elementos = soup.select('label.product__sizes__button')
        if formato_elementos:
            # Pega o formato do botão selecionado ou do primeiro botão
            for elem in formato_elementos:
                if 'active' in elem.get('class', []):
                    formato = elem.get_text(strip=True)
                    break
            
            # Se não encontrou nenhum botão ativo, usa o primeiro
            if not formato and formato_elementos:
                formato = formato_elementos[0].get_text(strip=True)
        
        # Se não encontrou nos botões, procura nas informações técnicas
        if not formato:
            for item in itens_info:
                span_nome = item.find('span', class_='product__technical__informations__name')
                span_valor = item.find('span', class_='product__technical__informations__value')
                if span_nome and span_valor:
                    label = ''.join(t for t in span_nome.find_all(text=True, recursive=False)).strip().lower()
                    if label in ['formato', 'tamanho', 'dimensão', 'dimensao']:
                        formato = span_valor.get_text(strip=True)
                        break
        
        # Se ainda não encontrou, procura em qualquer lugar da página
        if not formato:
            for text in soup.stripped_strings:
                if re.search(r'\d+(?:,\d+)?[Xx]\d+(?:,\d+)?(?:cm)?', text.replace(' ', '')):
                    formato = extrair_formato(text)
                    break
        
        if formato:
            print(f"[ℹ] Formato: {formato}")
        else:
            print(f"[⚠] Aviso: Formato não encontrado")
        
        # === Nome da pasta: "Produto - Acabamento Formato。" ===
        # Windows não permite nomes terminando em ponto ".", por isso usamos o unicode ideográfico full stop '。'.
        nome_base = nome_produto
        if acabamento:
            nome_base += f" - {acabamento}"
        if formato:
            nome_base += f" {formato}"
            
        nome_base += "。"
        
        print(f"[ℹ] Nome da pasta: {nome_base}")
        os.makedirs(nome_base, exist_ok=True)

        # === Download da imagem principal ===
        img = soup.select_one('div.swiper-slide img[src]')
        if img:
            url_img = urljoin(link, img['src'])
            baixar_arquivo(
                url_img, nome_base,
                cookies=driver.get_cookies(),
                headers={
                    'User-Agent': driver.execute_script('return navigator.userAgent'),
                    'Referer': link
                }
            )

        # === Screenshot ===
        tirar_screenshot_full(driver, os.path.join(nome_base, 'screenshot.png'))

        # === Downloads técnicos (PDF) ===
        for a in soup.find_all('a', href=True):
            href = a['href']
            texto_link = a.get_text(strip=True).lower()
            if href.lower().endswith('.pdf') or '/download/' in href or 'ficha técnica' in texto_link or 'guia' in texto_link:
                url_download = urljoin(link, href)
                nome_arquivo = a.get('download') or os.path.basename(urlparse(href).path)
                if not nome_arquivo.lower().endswith('.pdf'):
                    nome_arquivo += '.pdf'
                baixar_arquivo(
                    url_download, nome_base, nome_arquivo=nome_arquivo,
                    cookies=driver.get_cookies(),
                    headers={
                        'User-Agent': driver.execute_script('return navigator.userAgent'),
                        'Referer': link
                    }
                )

        # === Downloads adicionais (SketchUp, faces etc.) ===
        for botao in driver.find_elements(By.CSS_SELECTOR, 'a.download-link'):
            try:
                tipo = botao.find_element(By.TAG_NAME, 'h5').text.strip().lower()
            except:
                continue
            if tipo in DOWNLOAD_TYPES:
                url_extra = urljoin(link, botao.get_attribute('data-download-url'))
                ext = os.path.splitext(urlparse(url_extra).path)[1] or '.rar'
                nome_extra = f"{nome_base}_{tipo.replace(' ', '_')}{ext}"
                baixar_arquivo(
                    url_extra, nome_base, nome_arquivo=nome_extra,
                    cookies=driver.get_cookies(),
                    headers={
                        'User-Agent': driver.execute_script('return navigator.userAgent'),
                        'Referer': link
                    }
                )
                time.sleep(1)

    finally:
        driver.quit()


def ler_urls_do_arquivo(biancogres_links):
    """Lê URLs de um arquivo de texto, uma URL por linha."""
    try:
        with open(biancogres_links, 'r', encoding='utf-8') as f:
            # Lê todas as linhas, remove espaços em branco e filtra linhas vazias
            urls = [linha.strip() for linha in f.readlines()]
            urls = [url for url in urls if url and not url.startswith('#')]
            
            if not urls:
                print(f"[⚠] Aviso: Arquivo {biancogres_links} está vazio ou contém apenas comentários.")
                return []
                
            print(f"[ℹ] Lidas {len(urls)} URLs do arquivo {biancogres_links}")
            return urls
    except FileNotFoundError:
        print(f"[✘] Erro: Arquivo {biancogres_links} não encontrado.")
        # Cria um arquivo de exemplo
        with open(biancogres_links, 'w', encoding='utf-8') as f:
            f.write("# Lista de URLs para baixar (uma por linha)\n")
            f.write("# Linhas começando com # são comentários e serão ignoradas\n\n")
            f.write("https://www.biancogres.com.br/produto/abruzzo-massima-pro\n")
            f.write("# https://www.biancogres.com.br/produto/outro-produto\n")
        print(f"[ℹ] Criado arquivo de exemplo {biancogres_links}. Edite-o e execute o script novamente.")
        return []
    except Exception as e:
        print(f"[✘] Erro ao ler o arquivo {biancogres_links}: {e}")
        return []


if __name__ == '__main__':
    # Verifica se foi passado um arquivo de URLs como argumento
    if len(sys.argv) > 1:
        arquivo_urls = sys.argv[1]
    else:
        arquivo_urls = ARQUIVO_URLS
        print(f"[ℹ] Nenhum arquivo especificado. Usando o padrão: {arquivo_urls}")
    
    # Lê as URLs do arquivo
    urls = ler_urls_do_arquivo(arquivo_urls)
    
    if not urls:
        print("[✘] Nenhuma URL para processar. Saindo.")
        sys.exit(1)
    
    # Processa cada URL
    start_total = time.time()
    total_urls = len(urls)
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{total_urls}] Processando: {url}")
        try:
            start = time.time()
            baixar_dados(url)
            duration = time.time() - start
            print(f"[⏱] {duration:.2f}s para processar {url}")
        except Exception as e:
            print(f"[✘] Erro ao processar {url}: {e}")
            # Continua com a próxima URL
    
    total_time = time.time() - start_total
    print(f"\n[⏱] Total: {total_time:.2f}s para processar {total_urls} URLs")
    print(f"[ℹ] Média: {total_time/total_urls:.2f}s por URL")