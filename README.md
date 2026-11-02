# Eu Acuso — Simulador de juros, dívida e inflação

Aplicativo [Streamlit](https://streamlit.io) que executa as variáveis do artigo
**"Eu Acuso: uma proposta para eliminar os juros absurdos"**, de André Lara Resende
(Substack *Um Cético Esperançoso*, 25/09/2026):

<https://andrelararesende.substack.com/p/eu-acuso-uma-proposta-para-eliminar>

O app recalcula os números do texto, simula a dinâmica da dívida pública sob diferentes
cenários e testa a consistência das premissas (a fórmula neo-fisheriana, o canal cambial, o
spread transitório). Opcionalmente, um modelo local via [Ollama](https://ollama.com)
(`qwen2.5:3b`) escreve um comentário crítico a partir dos resultados.

> **Aviso:** este é um exercício de modelagem, não uma previsão nem uma recomendação de
> política econômica ou de investimento. Parte dos parâmetros são hipóteses do autor do
> código, não números do artigo (veja a seção [Parâmetros](#parâmetros)).

## Funcionalidades

| Aba | O que faz |
|---|---|
| **1 · Variáveis do artigo** | Recalcula juros/PIB, efeito "bola de neve", déficit nominal, economia fiscal e primário estabilizador, e compara com o que o artigo afirma. |
| **2 · Teste neo-fisheriano** | Aplica π = i − g à Selic em vários níveis e sinaliza inconsistências (por exemplo, inflação implícita acima da meta durante o spread de 2 pp). |
| **3 · Simulação de cenários** | Compara *Status quo*, *Proposta CFMN* e *Ajuste fiscal convencional* em dívida/PIB, déficit nominal, Selic e inflação. Inclui matriz de sensibilidade às hipóteses de inflação. |
| **4 · Comentário cético (Ollama)** | Envia os resultados ao `qwen2.5:3b` local e exibe uma análise crítica em português. |

## Como o modelo funciona

Simulação mensal. Resumo:

- **Selic.** No cenário da proposta, cai linearmente até `g_nominal_potencial + spread`
  (padrão: 3,0 + 2,5 + 2,0 = 7,5%) no prazo escolhido, e depois o spread é zerado
  gradualmente. Nos demais cenários, permanece constante.
- **Custo da dívida.** Média ponderada entre LFTs (reprecificam imediatamente com a Selic)
  e demais títulos (reprecificam conforme a taxa de rolagem anual).
- **Inflação.** O núcleo converge para π\*(i), conforme o modo escolhido, somado a um
  repasse do canal cambial:
  - *Âncora na meta*: π\* = meta.
  - *Fisher do artigo*: π\* = i − g real (premissa de que r → g).
  - *Fisher calibrado*: π\* = π₀ + Δi (juro real observado constante).
  - *Convencional invertido*: π\* = π₀ − β·Δi (cortar juros eleva a inflação).
- **Dívida/PIB.** `d' = d · (1 + custo) / (1 + g_nominal) − primário`, com
  `g_nominal = (1 + π)(1 + g_real) − 1`.

## Instalação

Requer Python 3.10 ou superior.

```bash
git clone <URL-DO-SEU-REPOSITORIO>
cd <NOME-DO-REPOSITORIO>

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Uso

```bash
streamlit run app_eu_acuso.py
```

O app abre em <http://localhost:8501>. Os parâmetros ficam na barra lateral.

### Ollama + qwen2.5:3b (opcional)

Só a aba 4 depende do Ollama. O restante funciona sem ele. O Ollama **não** é instalado pelo
`pip`: é um programa separado, que roda um servidor local.

**1. Instale o Ollama**

| Sistema | Comando / ação |
|---|---|
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` |
| macOS | Baixe em <https://ollama.com/download> ou use `brew install ollama` |
| Windows | Baixe o instalador em <https://ollama.com/download> |

Confirme a instalação:

```bash
ollama --version
```

**2. Baixe o modelo `qwen2.5:3b`** (download de aproximadamente 2 GB)

```bash
ollama pull qwen2.5:3b
```

**3. Teste o modelo**

```bash
ollama list                                  # o qwen2.5:3b deve aparecer na lista
ollama run qwen2.5:3b "Explique juros reais em uma frase."
```

**4. Deixe o servidor rodando**

```bash
ollama serve          # só se ainda não estiver rodando (no macOS/Windows o app já o inicia)
```

Para conferir que a API está no ar:

```bash
curl http://localhost:11434/api/tags
```

Na aba 4 do app, use **Testar conexão** para verificar. O endereço padrão é
`http://localhost:11434`; ambos (endereço e modelo) podem ser alterados na própria aba.
O modelo recebe apenas os números calculados pelo app, e a análise gerada por um modelo de
3B parâmetros deve ser conferida antes de ser usada para qualquer fim.

## Parâmetros

Na barra lateral, os parâmetros são divididos em dois grupos:

- 🟦 **Do artigo:** dívida bruta (R$ 10,9 tri; 82,5% do PIB), dívida líquida (R$ 9,2 tri),
  custo médio (12,68% a.a.), crescimento nominal (~7%), crescimento real potencial (2,5%),
  meta de inflação (3,0%), spread transitório (2 pp), queda da Selic em ~12 meses,
  participação das LFTs (mais da metade) e reservas (acima de US$ 350 bi).
- 🟨 **Hipóteses do código (não estão no artigo):** Selic atual, resultado primário,
  taxa de rolagem dos títulos não-LFT, prêmio sobre a Selic, prazo para zerar o spread,
  velocidade de ajuste da inflação, canal cambial (sensibilidade, neutralização pelo BC,
  repasse) e estoque de carry-trade. **Ajuste esses valores antes de tirar conclusões.**
  O mais sensível é a Selic atual.

## Limitações

- Modelo estilizado: sem choques, sem dinâmica de expectativas explícita, sem distinção
  completa entre dívida bruta e líquida (os juros simulados incidem sobre a dívida bruta).
- Participação das LFTs e prêmio de prazo constantes ao longo do horizonte.
- O canal cambial é uma regra simples de depreciação e repasse, não um modelo de câmbio.
- Os resultados dependem fortemente da hipótese de inflação escolhida, e a matriz de
  sensibilidade da aba 3 existe para tornar isso visível.

## Estrutura

```
.
├── app_eu_acuso.py     # aplicativo Streamlit
├── requirements.txt    # dependências
└── README.md
```

## Créditos

- Ideias e proposta: André Lara Resende, *Eu Acuso: uma proposta para eliminar os juros
  absurdos* (2026). O autor do artigo não participou deste código.
- Referência teórica citada no artigo: John H. Cochrane, *The Fiscal Theory of the Price
  Level* (Princeton University Press, 2023).

## Licença

Defina a licença do repositório (por exemplo, MIT) adicionando um arquivo `LICENSE`.

