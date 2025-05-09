#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import time
import urllib
from urllib.parse import urlparse, urljoin
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import sys

DOWNLOAD_TYPES = ['faces do produto', 'bloco de sketchup', 'paginação', 'ambiente']

# Nome do arquivo de URLs (padrão)
ARQUIVO_URLS = 'product_links.txt'

def limpar_nome(nome: str) -> str:
    """Limpa nome removendo espaços extras e caracteres inválidos."""
    nome = nome.replace('\n', ' ')
    nome = re.sub(r'\s+', ' ', nome)
    nome = re.sub(r'[\\/*?:"<>|]', '', nome)
    return nome.strip()


def extrair_formato(texto: str) -> str:
    """Extrai o formato no padrão 20X141,50cm ou 80,5X140cm do texto."""
    # Padrão específico para formatos como 20X141,50cm ou 80,5X140cm
    pattern = re.compile(r'(\d+,?\d*X\d+,?\d*cm)', re.IGNORECASE)
    match = pattern.search(texto.replace(' ', ''))
    return match.group(0) if match else ""


def baixar_arquivo(url: str, pasta: str, nome_arquivo: str = None, cookies=None, headers=None) -> None:
    """Baixa arquivo: imagens via urllib, outros (.rar/.zip) via requests."""
    if not nome_arquivo:
        nome_arquivo = os.path.basename(urlparse(url).path)
    caminho = os.path.join(pasta, nome_arquivo)
    ext = os.path.splitext(nome_arquivo)[1].lower()

   
    if ext in ['.jpg', '.jpeg', '.png']:
        try:
            os.makedirs(pasta, exist_ok=True)
            urllib.request.urlretrieve(url, caminho)
            print(f"[✔] Imagem baixada: {caminho}")
        except Exception as e:
            print(f"[✘] Erro ao baixar imagem {url}: {e}")
        return

   
    sess = requests.Session()
    if cookies:
        for c in cookies:
            sess.cookies.set(c['name'], c['value'])
    hdr = headers or {'User-Agent': 'Mozilla/5.0'}

    tentativa, max_tentativas = 0, 3
    while tentativa < max_tentativas:
        tentativa += 1
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
            print(f"[✘] Tentativa {tentativa}/{max_tentativas} falhou: {e}")
            time.sleep(1)
    print(f"[✘] Não foi possível baixar {url} após {max_tentativas} tentativas.")


def tirar_screenshot_full(driver, caminho: str) -> None:
    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
    time.sleep(1)
    w = driver.execute_script('return document.body.scrollWidth')
    h = driver.execute_script('return document.body.scrollHeight')
    driver.set_window_size(w, h)
    driver.save_screenshot(caminho)
    print(f"[✔] Screenshot salvo em: {caminho}")


def extrair_especificacoes_villagres(soup: BeautifulSoup) -> dict:
    """Extrai as especificações técnicas específicas do site Villagres."""
    especificacoes = {}
    
    # Procura pelo título "Especificações Técnicas"
    specs_title = soup.find(string=re.compile('Especificações Técnicas', re.IGNORECASE))
    if specs_title:
        # Encontra a seção de especificações
        specs_section = specs_title.parent.parent
        
        # Procura por todos os h6 (títulos das especificações) e seus spans seguintes
        h6_elements = specs_section.find_all('h6', class_='font-weight-light texto-padrao text-uppercase')
        for h6 in h6_elements:
            # Obtém o título da especificação
            titulo = h6.text.strip().lower()
            
            # Obtém o valor da especificação (span seguinte)
            span = h6.find_next('span', class_='font-weight-light fw-bold')
            if span:
                valor = span.text.strip()
                
                # Armazena as especificações relevantes
                if 'produto' in titulo:
                    especificacoes['produto'] = valor
                elif 'formato' in titulo:
                    especificacoes['formato'] = valor
                elif 'material' in titulo:
                    especificacoes['material'] = valor
                elif 'superfície' in titulo or 'superficie' in titulo:
                    especificacoes['superficie'] = valor
                elif 'referência' in titulo or 'referencia' in titulo:
                    especificacoes['referencia'] = valor
    
    # Se não encontrou pelo método acima, tenta outro método
    if not especificacoes:
        # Procura por elementos h6 com texto específico
        produto_h6 = soup.find('h6', string=lambda s: s and 'produto' in s.lower())
        if produto_h6:
            span = produto_h6.find_next('span')
            if span:
                especificacoes['produto'] = span.text.strip()
        
        formato_h6 = soup.find('h6', string=lambda s: s and 'formato' in s.lower())
        if formato_h6:
            span = formato_h6.find_next('span')
            if span:
                especificacoes['formato'] = span.text.strip()
    
    # Tenta extrair do breadcrumb se ainda não encontrou o produto
    if 'produto' not in especificacoes:
        breadcrumb = soup.find('nav', id='timeline')
        if breadcrumb:
            # Procura pelo último item do breadcrumb (geralmente o nome do produto)
            last_item = breadcrumb.find('li', class_='breadcrumb-item active')
            if last_item:
                produto_text = last_item.text.strip()
                especificacoes['produto'] = produto_text
    
    return especificacoes


def baixar_dados(link: str) -> None:
    servico = Service(ChromeDriverManager().install())
    opts = webdriver.ChromeOptions()
    opts.add_argument('--headless')
    driver = webdriver.Chrome(service=servico, options=opts)
    driver.set_window_size(1920, 1080)

    try:
        driver.get(link)
        # Espera a página carregar completamente
        time.sleep(5)
        
        # Tenta clicar em botões de especificações técnicas, se existirem
        try:
            specs_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Especificações')] | //a[contains(text(), 'Especificações')]"))
            )
            specs_button.click()
            time.sleep(2)  # Espera as especificações carregarem
        except:
            # Se não encontrar o botão, continua normalmente
            pass
            
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extrai as especificações técnicas específicas do site Villagres
        especificacoes = extrair_especificacoes_villagres(soup)
        
        # Extrai o nome do produto das especificações
        nome_produto = ""
        if 'produto' in especificacoes and especificacoes['produto']:
            nome_produto = especificacoes['produto']
        
        # Se não encontrou nas especificações, tenta outros métodos
        if not nome_produto:
            # Tenta extrair do título da página
            title = soup.find('title')
            if title:
                title_text = title.text.strip()
                # Procura por padrões como "Avilés - Natural" no título
                match = re.search(r'([A-Za-zÀ-ÖØ-öø-ÿ]+\s+-\s+[A-Za-zÀ-ÖØ-öø-ÿ]+)', title_text)
                if match:
                    nome_produto = match.group(1)
        
        # Limpa o nome do produto
        nome_produto = limpar_nome(nome_produto)
        
        # Extrai o formato das especificações
        formato = ""
        if 'formato' in especificacoes and especificacoes['formato']:
            formato = especificacoes['formato']
        
        # Se não encontrou nas especificações, tenta extrair de qualquer texto da página
        if not formato:
            for text in soup.stripped_strings:
                formato_encontrado = extrair_formato(text)
                if formato_encontrado:
                    formato = formato_encontrado
                    break
        
        # Adiciona "Externo" se for um produto externo
        ambiente = "Externo" if "externo" in link.lower() or "externo" in driver.page_source.lower() else ""
        
        # Monta o nome da pasta no formato desejado: "Nome - Formato"
        nome_base = nome_produto
        if ambiente:
            nome_base += f" - {ambiente}"
        
        # Adiciona o formato no final do nome da pasta
        if formato:
            nome_base += f" - {formato}"
        
        # Verifica se há caracteres especiais codificados em URL e decodifica
        nome_base = urllib.parse.unquote(nome_base)
        
        # Remove caracteres inválidos para nomes de pasta
        nome_base = re.sub(r'[\\/*?:"<>|]', '', nome_base)
        
        # Verifica se o nome da pasta está vazio ou inválido
        if not nome_base or nome_base.isspace() or len(nome_base) < 3:
            # Usa um nome genérico baseado na URL
            url_path = urlparse(link).path.strip('/').split('/')
            if len(url_path) >= 2:
                produto = urllib.parse.unquote(url_path[-2]).replace('-', ' ').title()
                nome_base = f"Produto {produto}"
            else:
                # Último recurso: usa um timestamp
                nome_base = f"Produto {int(time.time())}"
            
        # Limita o tamanho do nome da pasta para evitar erros
        nome_base = nome_base[:150]  # Limita a 150 caracteres
            
        print(f"[ℹ] Nome da pasta: {nome_base}")
        os.makedirs(nome_base, exist_ok=True)

        # Baixa a imagem principal
        img = soup.find('img', style=lambda s: s and 'object-fit: contain' in s)
        if img and img.get('src'):
            url_img = urljoin(link, img['src'])
            baixar_arquivo(
                url_img, nome_base,
                cookies=driver.get_cookies(),
                headers={'User-Agent': driver.execute_script("return navigator.userAgent;"), 'Referer': link}
            )

        # Tira screenshot da página
        tirar_screenshot_full(driver, os.path.join(nome_base, 'screenshot.png'))

        # Processa os botões de download
        botoes = driver.find_elements(By.CSS_SELECTOR, 'a.download-link')
        for botao in botoes:
            try:
                txt = botao.find_element(By.TAG_NAME, 'h5').text.strip().lower()
            except:
                continue
            
            # Verifica se o tipo de download é válido
            if txt in DOWNLOAD_TYPES:
                driver.execute_script("arguments[0].scrollIntoView();", botao)
                rel = botao.get_attribute('data-download-url')
                full = urljoin(link, rel)

                # Define o nome do arquivo (não da pasta)
                if txt in ['faces do produto', 'bloco de sketchup']:
                    ext = os.path.splitext(urlparse(full).path)[1] or '.rar'
                    if txt == 'bloco de sketchup':
                        nome_arquivo = f"{nome_base} - BLOCO DE SKETCHUP{ext}"
                    else:
                        nome_arquivo = f"{nome_base}_{limpar_nome(txt)}{ext}"
                else:
                    nome_arquivo = f"{nome_base}_{limpar_nome(txt)}.jpg"

                # Baixa o arquivo na pasta correta (nome_base)
                baixar_arquivo(
                    full, nome_base,
                    nome_arquivo=nome_arquivo,
                    cookies=driver.get_cookies(),
                    headers={'User-Agent': driver.execute_script("return navigator.userAgent;"), 'Referer': link}
                )
                time.sleep(1)

    finally:
        driver.quit()


def ler_urls_do_arquivo(nome_arquivo):
    """Lê URLs de um arquivo de texto, uma URL por linha."""
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            # Lê todas as linhas, remove espaços em branco e filtra linhas vazias
            urls = [linha.strip() for linha in f.readlines()]
            urls = [url for url in urls if url and not url.startswith('#')]
            
            if not urls:
                print(f"[⚠] Aviso: Arquivo {nome_arquivo} está vazio ou contém apenas comentários.")
                return []
                
            print(f"[ℹ] Lidas {len(urls)} URLs do arquivo {nome_arquivo}")
            return urls
    except FileNotFoundError:
        print(f"[✘] Erro: Arquivo {nome_arquivo} não encontrado.")
        # Cria um arquivo de exemplo
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            f.write("# Lista de URLs para baixar (uma por linha)\n")
            f.write("# Linhas começando com # são comentários e serão ignoradas\n\n")
            f.write("https://villagres.com.br/PT/produtos/naturale/alameda/200021a\n")
            f.write("# https://villagres.com.br/PT/produtos/outro-produto/outro-modelo/codigo\n")
        print(f"[ℹ] Criado arquivo de exemplo {nome_arquivo}. Edite-o e execute o script novamente.")
        return []
    except Exception as e:
        print(f"[✘] Erro ao ler o arquivo {nome_arquivo}: {e}")
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
