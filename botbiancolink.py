import asyncio
from playwright.async_api import async_playwright

async def main():
    base_url = 'https://www.biancogres.com.br/pt_BR/produtos'
    output_file = 'biancogres_links.txt'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(base_url)
        await page.wait_for_load_state('networkidle')

        # Clicar em "Ver mais" até não existir mais
        while True:
            try:
                btn = page.locator('button.products-gallery__button').first
                # Espera botão visível e clicável
                await btn.wait_for(state='visible', timeout=5000)
                await btn.click()
                print('[INFO] Clique em Ver mais executado')
                # Aguarda carregamento de novos itens
                await page.wait_for_timeout(1000)
            except Exception:
                print('[INFO] Não há mais botões Ver mais')
                break

        # Coletar todos os links dos itens de produto
        items = page.locator('a.products-gallery__item')
        hrefs = await items.evaluate_all('els => els.map(e => e.href.trim())')
        # Remover duplicados e vazios
        unique_hrefs = [h for h in dict.fromkeys(hrefs) if h]

        # Salvar em arquivo
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in unique_hrefs:
                f.write(url + '\n')

        print(f'[RESULT] {len(unique_hrefs)} links salvos em {output_file}')
        await browser.close()

if __name__ == '__main__':
    # Pré-requisitos:
    # pip install playwright
    # playwright install
    asyncio.run(main())
