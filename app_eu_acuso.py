# -*- coding: utf-8 -*-
"""
Simulador do artigo de André Lara Resende, "Eu Acuso: uma proposta para eliminar os juros absurdos"
(Substack "Um Cético Esperançoso", 25/09/2026).

Executar:
    pip install streamlit pandas numpy requests
    streamlit run app_eu_acuso.py

Ollama (opcional, só para a aba de comentário crítico):
    ollama serve
    ollama pull qwen2.5:3b
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Eu Acuso — Simulador de juros e dívida", layout="wide")

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------
CEN_STATUS = "Status quo (Selic constante)"
CEN_PROPOSTA = "Proposta CFMN (Lara Resende)"
CEN_AJUSTE = "Ajuste fiscal convencional"
CENARIOS = [CEN_STATUS, CEN_PROPOSTA, CEN_AJUSTE]

MODOS = [
    "Âncora na meta (π* = meta)",
    "Fisher do artigo (π* = i − g real)",
    "Fisher calibrado (π* = π₀ + Δi)",
    "Convencional invertido (π* = π₀ − β·Δi)",
]

def mostrar_df(df, **kw):
    """Compatível com versões novas (width='stretch') e antigas (use_container_width) do Streamlit."""
    try:
        st.dataframe(df, width="stretch", **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kw)

# ----------------------------------------------------------------------------
# Barra lateral — variáveis
# ----------------------------------------------------------------------------
st.sidebar.title("Variáveis")
st.sidebar.caption("🟦 = números que estão no artigo 🟨 = outras hipóteses")

with st.sidebar.expander("🟦 Dívida, juros e PIB (artigo)", expanded=True):
    div_brl = st.number_input("Dívida bruta DBGG (R$ tri)", 0.1, 100.0, 10.9, 0.1)
    div_pib = st.number_input("Dívida bruta (% PIB)", 1.0, 300.0, 82.5, 0.5)
    div_liq = st.number_input("Dívida líquida DLSP (R$ tri)", 0.1, 100.0, 9.2, 0.1)
    custo = st.number_input("Custo médio da dívida (% a.a.)", 0.0, 50.0, 12.68, 0.01)
    pib_nom = st.number_input("Crescimento nominal atual do PIB (% a.a.)", 0.0, 30.0, 7.0, 0.1)
    g_real = st.number_input("Crescimento real potencial (% a.a.)", 0.0, 10.0, 2.5, 0.1)
    share_lft = st.slider("Participação das LFTs na dívida (%)", 0, 100, 55, 1,
                          help="Artigo: 'mais da metade'.") / 100

with st.sidebar.expander("🟦 Proposta do CFMN (artigo)", expanded=True):
    meta = st.number_input("Meta de inflação (% a.a.)", 0.0, 15.0, 3.0, 0.1)
    spread0 = st.number_input("Spread transitório de segurança (pp)", 0.0, 10.0, 2.0, 0.1)
    glide = st.number_input("Meses para a queda gradual da Selic", 1, 60, 12, 1)
    anos_spread = st.number_input("Anos para zerar o spread", 1, 10, 4, 1,
                                  help="O artigo diz 'gradualmente reduzido até ser eliminado' e "
                                       "fala em metas de 4 a 5 anos. O prazo exato é hipótese.")
    horizonte = st.number_input("Horizonte da simulação (anos)", 3, 30, 10, 1)

with st.sidebar.expander("🟨 Selic etc."):
    selic0 = st.number_input("Selic atual (% a.a.)", 0.0, 40.0, 14.0, 0.25,
                             help="Ajuste ao valor vigente.")
    prim0 = st.number_input("Resultado primário (% PIB; negativo = déficit)", -5.0, 5.0, -0.5, 0.1,
                            help="Artigo: 'ligeiramente negativo'.")
    rollover = st.slider("Rolagem anual dos títulos não-LFT (%)", 5, 100, 25, 5) / 100
    premio = st.number_input("Prêmio sobre a Selic nos títulos não-LFT (pp)", -3.0, 10.0, 0.0, 0.1)
    risco = st.number_input("Prêmio de risco extra SÓ na proposta (pp)", 0.0, 10.0, 0.0, 0.1,
                            help="Teste de estresse: e se o mercado não comprar a credibilidade do CFMN?")
    kappa = st.number_input("Velocidade de ajuste da inflação (1/ano)", 0.1, 5.0, 1.0, 0.1)
    beta = st.number_input("β do modo 'convencional invertido'", 0.0, 2.0, 0.3, 0.05)
    ajuste = st.number_input("Ajuste fiscal convencional: superávit primário extra (pp PIB)",
                             0.0, 6.0, 1.0, 0.1)

with st.sidebar.expander("🟨 Canal cambial (hipóteses)"):
    gamma = st.number_input("Depreciação (%) por pp de corte da Selic", 0.0, 10.0, 1.5, 0.1)
    offset = st.slider("Fração da depreciação neutralizada pelo BC (%)", 0, 100, 50, 5) / 100
    passthru = st.number_input("Repasse câmbio → inflação", 0.0, 1.0, 0.15, 0.01)
    reservas = st.number_input("Reservas internacionais (US$ bi) — artigo: >350", 0.0, 2000.0, 350.0, 10.0)
    carry = st.number_input("Estoque de carry-trade (US$ bi) — hipótese", 0.0, 2000.0, 150.0, 10.0)
    saida = st.slider("Fração do carry-trade que sai (%)", 0, 100, 30, 5) / 100

# Parâmetros derivados
pi0 = ((1 + pib_nom / 100) / (1 + g_real / 100) - 1) * 100  # inflação implícita (deflator)
g_pot_nom = meta + g_real  # crescimento nominal potencial, como no artigo (3,0 + 2,5 = 5,5)

P = dict(
    div_pib=div_pib, custo=custo, g_real=g_real, lft=share_lft, meta=meta, spread0=spread0,
    glide=int(glide), anos_spread=int(anos_spread), selic0=selic0, prim0=prim0,
    rollover=rollover, premio=premio, risco=risco, kappa=kappa, beta=beta, ajuste=ajuste,
    gamma=gamma, offset=offset, passthru=passthru, pi0=pi0, g_pot_nom=g_pot_nom,
)


# ----------------------------------------------------------------------------
# Modelo
# ----------------------------------------------------------------------------
def pi_estrela(i: float, modo: str, p: dict) -> float:
    """Inflação de longo prazo implícita pela Selic i, conforme a hipótese escolhida."""
    if modo == MODOS[0]:
        return p["meta"]
    if modo == MODOS[1]:
        return i - p["g_real"]
    if modo == MODOS[2]:
        return p["pi0"] + (i - p["selic0"])
    return p["pi0"] - p["beta"] * (i - p["selic0"])


def simular(p: dict, cenario: str, modo: str, anos: int) -> pd.DataFrame:
    H = int(anos * 12)
    t = np.arange(H + 1)
    i0 = p["selic0"]

    # 1) Trajetória da Selic
    if cenario == CEN_PROPOSTA:
        alvo0 = p["g_pot_nom"] + p["spread0"]
        sel = np.where(t <= p["glide"], i0 + (alvo0 - i0) * t / p["glide"], alvo0)
        dec = max(p["anos_spread"] * 12, 1)
        extra = np.clip((t - p["glide"]) / dec, 0, 1)
        sel = np.where(t > p["glide"], alvo0 - p["spread0"] * extra, sel)
    else:
        sel = np.full(H + 1, float(i0))

    # 2) Primário (% PIB, positivo = superávit)
    prim = p["prim0"] + (p["ajuste"] if cenario == CEN_AJUSTE else 0.0)

    # 3) Canal cambial: depreciação acumulada e repasse à inflação (variação em 12 meses)
    nivel_cambio = p["gamma"] * (1 - p["offset"]) * np.maximum(i0 - sel, 0)
    defasado = np.concatenate([np.zeros(12), nivel_cambio[:-12]]) if H + 1 > 12 else np.zeros(H + 1)
    bump = p["passthru"] * (nivel_cambio - defasado)

    # 4) Inflação: núcleo converge para π*(i); soma-se o choque cambial
    pi_core = np.zeros(H + 1)
    pi_core[0] = p["pi0"]
    for k in range(H):
        alvo = max(pi_estrela(sel[k], modo, p), 0.0)
        pi_core[k + 1] = pi_core[k] + (p["kappa"] / 12) * (alvo - pi_core[k])
    pi = pi_core + bump

    # 5) Dinâmica da dívida (% PIB), passo mensal
    s = p["lft"]
    c_out = (p["custo"] - s * i0) / (1 - s) if s < 1 else 0.0  # custo implícito dos não-LFT
    prem = p["premio"] + (p["risco"] if cenario == CEN_PROPOSTA else 0.0)

    d = np.zeros(H + 1)
    d[0] = p["div_pib"]
    cost = np.zeros(H + 1)
    gnom = np.zeros(H + 1)
    for k in range(H + 1):
        cost[k] = s * sel[k] + (1 - s) * c_out
        gnom[k] = ((1 + pi[k] / 100) * (1 + p["g_real"] / 100) - 1) * 100
        if k < H:
            fator = ((1 + cost[k] / 100) / (1 + gnom[k] / 100)) ** (1 / 12)
            d[k + 1] = d[k] * fator - prim / 12
            c_out += (p["rollover"] / 12) * (sel[k] + prem - c_out)

    juros_pib = d * cost / 100
    return pd.DataFrame({
        "ano": t / 12,
        "Selic (%)": sel,
        "Custo médio da dívida (%)": cost,
        "Inflação (%)": pi,
        "Crescimento nominal (%)": gnom,
        "Dívida bruta/PIB (%)": d,
        "Juros s/ dív. bruta (% PIB)": juros_pib,
        "Déficit nominal (% PIB)": juros_pib - prim,
    }).set_index("ano")


# ----------------------------------------------------------------------------
# Cálculos "estáticos" do artigo
# ----------------------------------------------------------------------------
pib_tri = div_brl / (div_pib / 100)
juros_tri = div_brl * custo / 100
juros_pib_bruta = juros_tri / pib_tri * 100
liq_pib = div_liq / pib_tri * 100
juros_pib_liq = liq_pib * custo / 100
cresc_razao = ((1 + custo / 100) / (1 + pib_nom / 100) - 1) * 100
bola_neve = div_pib * ((custo - pib_nom) / 100) / (1 + pib_nom / 100)  # pp PIB / ano
alvo_proposta = g_pot_nom + spread0
economia_estatica = (custo - alvo_proposta) / 100 * div_pib
prim_estab_proposta = div_pib * ((alvo_proposta - g_pot_nom) / 100) / (1 + g_pot_nom / 100)
r_obs = selic0 - pi0
cobertura = reservas / (carry * saida) if carry * saida > 0 else float("inf")

# ----------------------------------------------------------------------------
# Cabeçalho
# ----------------------------------------------------------------------------
st.title("Simulador do artigo Eu Acuso: uma proposta para eliminar os juros absurdos, de André Lara Resende")
st.caption("Executa as variáveis e gera um relatório.")
    

aba1, aba2, aba3, aba4 = st.tabs([
    "1 · Variáveis do artigo", "2 · Teste neo-fisheriano", "3 · Simulação de cenários", "4 · Relatório cético"
])

# ----------------------------------------------------------------------------
# Aba 1
# ----------------------------------------------------------------------------
with aba1:
    st.subheader("Recalculando os números do texto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PIB implícito (R$ tri)", f"{pib_tri:,.1f}")
    c2.metric("Juros s/ dívida bruta", f"R$ {juros_tri:,.2f} tri", f"{juros_pib_bruta:.1f}% PIB")
    c3.metric("Juros s/ dívida líquida", f"{juros_pib_liq:.1f}% PIB", f"dív. líq. {liq_pib:.1f}% PIB")
    c4.metric("Efeito bola de neve", f"{bola_neve:.2f} pp PIB/ano",
              f"razão dívida/PIB cresce {cresc_razao:.1f}%/ano", delta_color="inverse")

    tabela = pd.DataFrame([
        ("Juros s/ dívida bruta (R$ tri)", "≈ 1,4", f"{juros_tri:.2f}"),
        ("Juros s/ dívida bruta (% PIB)", "10,5%", f"{juros_pib_bruta:.1f}%"),
        ("Dívida líquida (% PIB)", "69,1%", f"{liq_pib:.1f}%"),
        ("Juros s/ dívida líquida (% PIB)", "8,7%", f"{juros_pib_liq:.1f}%"),
        ("Crescimento da razão dívida/PIB", "≈ 5,7% a.a. (12,7 − 7)", f"{cresc_razao:.1f}% a.a. (composto)"),
        ("Déficit nominal (juros líq. + primário)", "≈ 10% PIB", f"{juros_pib_liq - prim0:.1f}% PIB"),
        ("Economia fiscal com Selic → 7,5%", "≈ 4% PIB/ano", f"{economia_estatica:.1f}% PIB/ano (estática, após rolagem total)"),
        ("Crescimento nominal potencial", "5,5% (3,0 + 2,5)", f"{g_pot_nom:.1f}%"),
    ], columns=["Variável", "Artigo", "Recalculado aqui"])
    mostrar_df(tabela, hide_index=True)

    st.info(
        f"**Primário que estabilizaria a razão dívida/PIB hoje:** {bola_neve:.1f}% do PIB. "
        f"**Com a Selic no alvo da proposta ({alvo_proposta:.1f}%) e crescimento potencial:** "
        f"{prim_estab_proposta:.1f}% do PIB. A proposta troca um ajuste que o artigo considera "
        "impossível por um ajuste bem menor — desde que a inflação e o mercado cooperem."
    )

    with st.expander("Mapa de variáveis do artigo"):
        st.markdown("""
| Símbolo | Significado | Papel no modelo |
|---|---|---|
| `i` | Selic (juro nominal) | Controlada pelo BC; custo das LFTs |
| `π` | Inflação | Núcleo converge para π*(i) + repasse cambial |
| `r` | Juro real | No longo prazo, tende a `g` (premissa do artigo) |
| `g` | Crescimento real potencial | 2,5% |
| `g_nom` | Crescimento nominal | (1+π)(1+g) − 1 |
| `d` | Dívida bruta/PIB | d' = d·(1+custo)/(1+g_nom) − primário |
| LFT | Título pós-fixado à Selic | Reprecifica na hora (dívida "curta") |
| CFMN | Conselho Fiscal e Monetário Nacional | Metas fiscais/monetárias de 4–5 anos |
| Banda | Selic ∈ [meta de inflação, crescimento nominal potencial] | 3,0% a 5,5% |
""")

# ----------------------------------------------------------------------------
# Aba 2
# ----------------------------------------------------------------------------
with aba2:
    st.subheader("Fisher, neo-Fisher e a aritmética que não fecha de graça")
    st.markdown(
        "Identidade: **i = r + π**. O artigo supõe que, no longo prazo, **r → g** e que r não depende de i. "
        "Logo **π = i − g**. Abaixo, o que essa fórmula diz, comparado com o que ela diria se "
        "calibrada no juro real **observado** (Selic − inflação)."
    )
    st.write(f"Juro real implícito hoje (hipótese de Selic): **{r_obs:.1f}%** · crescimento real potencial: **{g_real:.1f}%**")

    candidatos = sorted({round(x, 2) for x in [selic0, 12.0, 10.0, alvo_proposta, g_pot_nom, meta]}, reverse=True)
    linhas = []
    for i in candidatos:
        pa = i - g_real
        pc = pi0 + (i - selic0)
        linhas.append({
            "Selic i (%)": i,
            "π* artigo (i − g)": round(pa, 2),
            "π* calibrado (π₀ + Δi)": round(pc, 2),
            "Artigo vs meta (pp)": round(pa - meta, 2),
        })
    mostrar_df(pd.DataFrame(linhas), hide_index=True)

    alertas = []
    pi_trans = alvo_proposta - g_real
    if pi_trans > meta:
        alertas.append(
            f"Com Selic de {alvo_proposta:.1f}% (alvo + spread), a fórmula do artigo dá π = {pi_trans:.1f}%, "
            f"acima da meta de {meta:.1f}% e da inflação implícita atual ({pi0:.1f}%)."
        )
    pi_piso = meta - g_real
    alertas.append(
        f"No piso da banda (Selic = meta = {meta:.1f}%), a fórmula implica π = {pi_piso:.1f}%, "
        "não a meta. Só o teto da banda (crescimento nominal potencial) é coerente com a meta."
    )
    pi_hoje_formula = selic0 - g_real
    alertas.append(
        f"Aplicada à Selic de hoje ({selic0:.1f}%), a fórmula prevê π = {pi_hoje_formula:.1f}%, "
        f"contra {pi0:.1f}% observados. Ou r não converge para g, ou o 'longo prazo' é muito longo."
    )
    alertas.append(
        f"Cobertura cambial: reservas de US$ {reservas:,.0f} bi vs saída hipotética de US$ {carry * saida:,.0f} bi "
        f"→ {cobertura:.1f}x. A munição existe; resta saber a pontaria."
    )
    for a in alertas:
        st.warning(a)

# ----------------------------------------------------------------------------
# Aba 3
# ----------------------------------------------------------------------------
with aba3:
    st.subheader("Cenários lado a lado")
    modo = st.radio("Como a inflação reage à Selic?", MODOS, index=0, horizontal=False)
    anos = int(horizonte)

    res = {c: simular(P, c, modo, anos) for c in CENARIOS}

    def ponto(df, ano):
        return df.loc[min(ano, df.index.max())]

    cols = st.columns(3)
    for col, c in zip(cols, CENARIOS):
        df = res[c]
        col.markdown(f"**{c}**")
        col.metric(f"Dívida/PIB em {anos} anos", f"{df['Dívida bruta/PIB (%)'].iloc[-1]:.1f}%",
                   f"{df['Dívida bruta/PIB (%)'].iloc[-1] - div_pib:+.1f} pp", delta_color="inverse")
        col.metric("Déficit nominal no ano 5", f"{ponto(df, 5)['Déficit nominal (% PIB)']:.1f}% PIB")
        col.metric("Inflação no ano 5", f"{ponto(df, 5)['Inflação (%)']:.1f}%")

    def junta(coluna):
        return pd.DataFrame({c: res[c][coluna] for c in CENARIOS})

    g1, g2 = st.columns(2)
    g1.markdown("**Dívida bruta / PIB (%)**")
    g1.line_chart(junta("Dívida bruta/PIB (%)"))
    g2.markdown("**Déficit nominal (% PIB)**")
    g2.line_chart(junta("Déficit nominal (% PIB)"))
    g3, g4 = st.columns(2)
    g3.markdown("**Selic (%)**")
    g3.line_chart(junta("Selic (%)"))
    g4.markdown("**Inflação (%)**")
    g4.line_chart(junta("Inflação (%)"))

    st.markdown("### Sensibilidade: dívida/PIB no horizonte × hipótese de inflação")
    matriz = {}
    for m in MODOS:
        matriz[m] = {c: simular(P, c, m, anos)["Dívida bruta/PIB (%)"].iloc[-1] for c in CENARIOS}
    mostrar_df(pd.DataFrame(matriz).T.round(1))
    st.caption(
        "Leitura cética: se o resultado da proposta muda de 'milagre' para 'desastre' conforme a "
        "hipótese de inflação, o que o modelo mostra é a hipótese, não a economia."
    )

    with st.expander("Dados completos (proposta)"):
        mostrar_df(res[CEN_PROPOSTA].iloc[::6].round(2))

# ----------------------------------------------------------------------------
# Aba 4 — Ollama
# ----------------------------------------------------------------------------
with aba4:
    st.subheader("Comentário cético com Ollama / qwen2.5:3b")
    st.caption("Um modelo de 3B parâmetros comentando macroeconomia: ironia involuntária garantida. "
               "Ele só recebe os números calculados aqui; confira tudo.")
    host = st.text_input("Endereço do Ollama", "http://localhost:11434")
    modelo = st.text_input("Modelo", "qwen2.5:3b")

    if st.button("Testar conexão"):
        try:
            r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=5)
            nomes = [m["name"] for m in r.json().get("models", [])]
            st.success(f"Ollama respondeu. Modelos: {', '.join(nomes) or '(nenhum)'}")
        except Exception as e:  # noqa: BLE001
            st.error(f"Sem conexão: {e}")

    resumo = {
        "dados_artigo": {
            "divida_bruta_pib": div_pib, "custo_medio_divida": custo,
            "juros_pib_bruta": round(juros_pib_bruta, 1), "juros_pib_liquida": round(juros_pib_liq, 1),
            "crescimento_nominal_pib": pib_nom, "bola_de_neve_pp_pib": round(bola_neve, 2),
            "economia_fiscal_estatica_pp_pib": round(economia_estatica, 1),
        },
        "proposta": {
            "selic_alvo_inicial": alvo_proposta, "selic_final_banda": g_pot_nom,
            "meta_inflacao": meta, "primario_estabilizador_pp_pib": round(prim_estab_proposta, 1),
        },
        "alertas_de_consistencia": alertas,
        "hipotese_de_inflacao_usada": modo,
        "divida_pib_no_horizonte": {c: round(res[c]["Dívida bruta/PIB (%)"].iloc[-1], 1) for c in CENARIOS},
        "horizonte_anos": anos,
        "matriz_sensibilidade": {m: {c: round(v, 1) for c, v in linha.items()} for m, linha in matriz.items()},
    }
    with st.expander("O que será enviado ao modelo"):
        st.json(resumo)

    SISTEMA = (
        "Você é um analista econômico brasileiro, cético e irônico, mas rigoroso. "
        "Responda em português do Brasil. Use SOMENTE os números fornecidos; não invente dados. "
        "Estrutura: (1) o que o artigo afirma, em 2 frases; (2) o que a simulação mostra; "
        "(3) três fragilidades das premissas, citando os alertas; (4) o que seria preciso "
        "acontecer para a proposta funcionar. Seja breve (no máximo 250 palavras) e ácido sem ser leviano."
    )

    if st.button("Gerar comentário", type="primary"):
        prompt = "Analise estes resultados de simulação:\n" + json.dumps(resumo, ensure_ascii=False, indent=2)
        try:
            with st.spinner("Consultando o modelo local…"):
                r = requests.post(
                    f"{host.rstrip('/')}/api/generate",
                    json={"model": modelo, "system": SISTEMA, "prompt": prompt, "stream": False,
                          "options": {"temperature": 0.4, "num_ctx": 4096}},
                    timeout=600,
                )
                r.raise_for_status()
                st.session_state["comentario"] = r.json().get("response", "")
        except Exception as e:  # noqa: BLE001
            st.error(f"Falha ao chamar o Ollama: {e}")

    if st.session_state.get("comentario"):
        st.markdown(st.session_state["comentario"])
