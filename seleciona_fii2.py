# seleciona_fii2.py
# ==========================================
# Exibe página web com formulário de filtros.
# Mostra os valores padrão nos campos logo ao abrir.
# Remove a coluna de endereço e permite baixar Excel
# gerado em memória (sem salvar no disco).
# ==========================================

from flask import Flask, render_template_string, request, send_file
import pandas as pd
import requests
from bs4 import BeautifulSoup
import unicodedata
import io

app = Flask(__name__)

# -----------------------------------------
# Função para obter os dados do Fundamentus
# -----------------------------------------
def obter_dados_fii():
    url = "https://www.fundamentus.com.br/fii_resultado.php"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    resp.encoding = 'latin1'

    if resp.status_code != 200:
        raise Exception(f"Erro ao acessar {url}, status: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")
    tabela = soup.find("table")

    headers_cols = [th.get_text().strip() for th in tabela.find("thead").find_all("th")]
    dados = []
    for tr in tabela.find("tbody").find_all("tr"):
        cols = [td.get_text().strip() for td in tr.find_all("td")]
        if len(cols) == len(headers_cols):
            dados.append(cols)

    df = pd.DataFrame(dados, columns=headers_cols)

    # normalizar nomes de colunas
    def normaliza_coluna(col):
        return unicodedata.normalize("NFKD", col).encode("ASCII", "ignore").decode("utf-8").replace(" ", "")

    df.columns = [normaliza_coluna(c) for c in df.columns]
    return df


# -----------------------------------------
# Página principal (formulário + resultados)
# -----------------------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    # 🔹 Valores padrão dos filtros
    filtros = {
        "vacancia": 5,
        "pvp": 1,
        "dy": 9,
        "liquidez": 500000,
        "valormercado": 5000000,
        "qtdimoveis": 3
    }

    # 🔹 Atualiza com valores informados pelo usuário
    if request.method == "POST":
        for key in filtros:
            valor = request.form.get(key)
            if valor not in [None, ""]:
                try:
                    filtros[key] = float(valor)
                except ValueError:
                    pass

    # 🔹 Obtém dados do Fundamentus
    df = obter_dados_fii()

    # 🔹 Remove qualquer coluna que contenha "endere"
    colunas_remover = [c for c in df.columns if "endere" in c.lower()]
    if colunas_remover:
        df = df.drop(columns=colunas_remover)

    # Define colunas principais
    col_vacancia = "VacanciaMedia"
    col_pvp = "P/VP"
    col_dy = "DividendYield"
    col_liquidez = "Liquidez"
    col_valormercado = "ValordeMercado"
    col_qtdimoveis = "Qtddeimoveis"

    # Conversão numérica
    def limpa_numero(valor):
        if isinstance(valor, str):
            return valor.replace('.', '').replace('%', '').replace(',', '.')
        return valor

    for col in [col_vacancia, col_pvp, col_dy, col_liquidez, col_valormercado, col_qtdimoveis]:
        if col in df.columns:
            df[col] = df[col].apply(limpa_numero)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Aplicar filtros
    df_filtrado = df[
        (df[col_vacancia] < filtros["vacancia"]) &
        (df[col_pvp] <= filtros["pvp"]) &
        (df[col_dy] > filtros["dy"]) &
        (df[col_liquidez] > filtros["liquidez"]) &
        (df[col_valormercado] >= filtros["valormercado"]) &
        (df[col_qtdimoveis] >= filtros["qtdimoveis"])
    ]

    # Criar ranking e score
    if not df_filtrado.empty:
        df_filtrado = df_filtrado.sort_values(by=col_dy, ascending=False).reset_index(drop=True)
        df_filtrado["PosicaoDY"] = df_filtrado.index + 1
        df_filtrado = df_filtrado.sort_values(by=col_pvp, ascending=True).reset_index(drop=True)
        df_filtrado["PosicaoPVP"] = df_filtrado.index + 1
        df_filtrado["Score"] = (df_filtrado["PosicaoDY"] * 0.6) + (df_filtrado["PosicaoPVP"] * 0.4)
        df_filtrado = df_filtrado.sort_values(by="Score", ascending=True).reset_index(drop=True)

    # 🔹 Armazena o resultado filtrado em memória (para download)
    global ultimo_resultado
    ultimo_resultado = df_filtrado.copy()

    # Gerar HTML da tabela
    tabela_html = df_filtrado.to_html(classes="table table-striped", index=False) if not df_filtrado.empty else "<p>Nenhum FII encontrado com esses critérios.</p>"

    # HTML completo
    html = f"""
    <html>
    <head>
        <title>Seleção de FIIs</title>
        <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    </head>
    <body class="container mt-4">
        <h1>📊 Seleção de FIIs com base em critérios personalizados</h1>

        <!-- Formulário com valores visíveis -->
        <form method="POST" class="row g-3 mb-4">
            <div class="col-md-2">
                <label class="form-label">Vacância &lt; (%)</label>
                <input type="number" step="0.1" name="vacancia" class="form-control" value="{filtros['vacancia']}">
            </div>
            <div class="col-md-2">
                <label class="form-label">P/VP ≤</label>
                <input type="number" step="0.01" name="pvp" class="form-control" value="{filtros['pvp']}">
            </div>
            <div class="col-md-2">
                <label class="form-label">Dividend Yield &gt; (%)</label>
                <input type="number" step="0.1" name="dy" class="form-control" value="{filtros['dy']}">
            </div>
            <div class="col-md-2">
                <label class="form-label">Liquidez &gt;</label>
                <input type="number" step="1000" name="liquidez" class="form-control" value="{filtros['liquidez']}">
            </div>
            <div class="col-md-2">
                <label class="form-label">Valor de Mercado ≥</label>
                <input type="number" step="100000" name="valormercado" class="form-control" value="{filtros['valormercado']}">
            </div>
            <div class="col-md-2">
                <label class="form-label">Qtd. Imóveis ≥</label>
                <input type="number" step="1" name="qtdimoveis" class="form-control" value="{filtros['qtdimoveis']}">
            </div>
            <div class="col-12">
                <button type="submit" class="btn btn-primary mt-3">🔍 Filtrar</button>
            </div>
        </form>

        <h4>Resultados ({len(df_filtrado)} registros encontrados)</h4>
        {tabela_html}

        <a href="/download" class="btn btn-success mt-3">⬇️ Baixar Excel</a>
    </body>
    </html>
    """

    return render_template_string(html)


# -----------------------------------------
# Download do Excel (gera direto da memória)
# -----------------------------------------
@app.route("/download")
def download():
    global ultimo_resultado
    if ultimo_resultado is None or ultimo_resultado.empty:
        return "Nenhum resultado disponível para download."

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        ultimo_resultado.to_excel(writer, index=False, sheet_name="FIIs")
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="fii_filtrado.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# Variável global para armazenar o último resultado
ultimo_resultado = None

if __name__ == "__main__":
    app.run(debug=True)
