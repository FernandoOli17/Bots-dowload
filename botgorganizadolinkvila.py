#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot para coletar todos os links de produtos Villagres:
- Entra na página principal (/produtos)
- Extrai coleções via pattern de URL
- Navega pelas coleções e subcoleções
- Coleta links finais de produtos
- Salva todos em um arquivo txt
"""
import asyncio
import re
from playwright.async_api import async_playwright

BASE_URL = 'https://villagres.com.br/PT/produtos'
OUTPUT_FILE = 'product_links.txt'
# Regex para detectar coleções: https://.../produtos/<colecao>
COLLECTION_REGEX = re.compile(r'^https://villagres\.com\.br/PT/produtos/[^/]+$')
# Regex para detectar subcoleções: https://.../produtos/<colecao>/<sub>
SUBCOL_REGEX = re.compile(r'^https://villagres\.com\.br/PT/produtos/[^/]+/[^/]+$')
# Regex para detectar produtos: https://.../produtos/<colecao>/<sub>/<codigo>
PRODUCT_REGEX = re.compile(r'^https://villagres\.com\.br/PT/produtos/[^/]+/[^/]+/[0-9A-Za-z]+$')

async def main():
    all_links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Página principal
        page = await context.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_load_state('networkidle')

        # 1) Coleta URLs de coleções
        urls = await page.evaluate(
            """
            Array.from(document.querySelectorAll('a[href*="/produtos/"]'))
                 .map(a => a.href.trim())
            """
        )
        collections = {u.rstrip('/') for u in urls if COLLECTION_REGEX.match(u.rstrip('/'))}
        print(f"[INFO] {len(collections)} coleções encontradas.")

       
        for col in sorted(collections):
            print(f"[INFO] Processando coleção: {col}")
            col_page = await context.new_page()
            await col_page.goto(col)
            await col_page.wait_for_load_state('networkidle')
            await col_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await col_page.wait_for_timeout(500)

            urls2 = await col_page.evaluate(
                """
                Array.from(document.querySelectorAll('a[href*="/produtos/"]'))
                     .map(a => a.href.trim())
                """
            )
            subs = {u.rstrip('/') for u in urls2 if SUBCOL_REGEX.match(u.rstrip('/'))}
            print(f"[INFO] └─ {len(subs)} subcoleções encontradas.")

            await col_page.close()

           
            for sub in sorted(subs):
                print(f"[INFO]   Processando subcoleção: {sub}")
                sub_page = await context.new_page()
                await sub_page.goto(sub)
                await sub_page.wait_for_load_state('networkidle')
                await sub_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await sub_page.wait_for_timeout(500)

                urls3 = await sub_page.evaluate(
                    """
                    Array.from(document.querySelectorAll('a[href*="/produtos/"]'))
                         .map(a => a.href.trim())
                    """
                )
                products = {u.rstrip('/') for u in urls3 if PRODUCT_REGEX.match(u.rstrip('/'))}
                print(f"[INFO]   └─ {len(products)} produtos encontrados.")
                all_links.update(products)

                await sub_page.close()

        # Salva resultados
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for link in sorted(all_links):
                f.write(link + '\n')

        print(f"[RESULT] Total de {len(all_links)} links de produto salvos em '{OUTPUT_FILE}'")
        await browser.close()

if __name__ == '__main__':
    # Antes de rodar:
    # pip install playwright
    # playwright install
    asyncio.run(main())
