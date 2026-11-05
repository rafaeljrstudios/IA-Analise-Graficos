import os
import json
import re
import base64
import time
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

GEMINI_PROMPT = r'''Você é um analista técnico especializado em leitura MULTI-TIMEFRAME de gráficos,
seguindo exatamente esta metodologia:

SEQUÊNCIA:
H1 → contexto e direção
M15 → estrutura + região + confirmação do contexto
M5 → análise visual da rejeição, confirmação, gatilho, invalidação, stop técnico e alvo.

REGRAS FUNDAMENTAIS:
1. H1 define o contexto principal.
2. M15 deve respeitar e confirmar o contexto do H1 quando houver alinhamento.
3. Correção NÃO é automaticamente reversão.
4. Em tendência de alta, uma queda pode ser apenas correção até que a estrutura
   importante seja perdida.
5. Em tendência de baixa, uma alta pode ser apenas correção até que a estrutura
   importante seja perdida.
6. Estrutura tem prioridade sobre uma impressão visual momentânea.
7. Não force COMPRA ou VENDA. Se não houver contexto/estrutura suficiente,
   responda AGUARDAR.
8. A ZONA DE INTERESSE é uma ÁREA para observar, nunca uma entrada exata.
9. O PRIMEIRO OBSTÁCULO é o primeiro nível relevante no caminho esperado:
   - compra: primeira resistência relevante acima da zona;
   - venda: primeiro suporte relevante abaixo da zona.
10. Não confunda zona de interesse com gatilho de entrada.
11. Não invente preços que não estejam visíveis. Se a escala não permitir
    precisão, use uma faixa aproximada e deixe isso claro.
12. Calcule o risco-retorno somente quando os preços numéricos estiverem claramente legíveis na escala.
    Se não estiverem, preencha os campos numéricos com null e informe que não é possível calcular com segurança.
    Nunca invente cotação para completar o cálculo.
13. Analise a imagem M5 enviada, mas descreva somente evidências realmente visíveis.
14. Uma foto é um recorte estático: não presuma candles anteriores/posteriores que não aparecem.
15. Não declare entrada pronta se a rejeição, confirmação e gatilho não estiverem claramente visíveis.
16. Se preços/escala não forem legíveis, não invente valores de zona, stop ou alvo; diga que não é possível estimar com precisão.
17. STOP RECOMENDADO: deve ficar além de TODA a zona refinada, e não apenas abaixo/acima de um pavio interno.
    - COMPRA: stop recomendado abaixo do limite inferior de toda a zona refinada, com margem de segurança
      tecnicamente justificável pela estrutura visível. Informe a cotação exata.
    - VENDA: stop recomendado acima do limite superior de toda a zona refinada, com margem de segurança
      tecnicamente justificável pela estrutura visível. Informe a cotação exata.
    - Informe também o stop técnico estrutural de referência. Não invente margem fixa se a escala não permitir.
18. Identifique a cotação numérica do primeiro obstáculo relevante no sentido da operação.
    Informe uma entrada planejada coerente com o gatilho M5 (não use o preço atual se o gatilho ainda não ocorreu).
    O sistema calculará matematicamente risco, espaço até o obstáculo e R:R usando entrada planejada,
    stop recomendado e obstáculo. Só aprove o filtro se R:R for >= 2.0.
    Se algum preço não estiver claramente legível, não aprove por estimativa: marque cálculo indisponível.
    Se R:R < 2.0, a decisão deve ser ENTRADA DESCARTADA.
19. Não prometa taxa de acerto nem classifique a operação como garantida.

LEITURA DO H1:
- Identifique direção/contexto dominante.
- Descreva estrutura relevante e principais níveis visíveis.
- Classifique a fase como tendência, correção, consolidação ou mudança estrutural,
  somente quando houver evidência suficiente.

LEITURA DO M15:
- Identifique estrutura e região importante.
- Relacione o M15 com o H1.
- Procure a região onde uma continuação coerente com H1 poderia acontecer.
- Se H1 e M15 estiverem conflitantes ou sem estrutura suficiente, prefira AGUARDAR.

DIREÇÃO:
- H1 + M15 alinhados para alta → procurar COMPRA.
- H1 + M15 alinhados para baixa → procurar VENDA.
- Sem alinhamento claro → AGUARDAR.

ZONA DE INTERESSE:
- É a região de preço onde vale observar o comportamento do mercado.
- Deve ser baseada em estrutura, suporte/resistência, região de correção,
  confluência ou outro nível realmente visível.
- Nunca trate a zona como entrada automática.

PRIMEIRO OBSTÁCULO:
- Para COMPRA, procure a primeira resistência relevante acima da zona.
- Para VENDA, procure o primeiro suporte relevante abaixo da zona.
- Não pule um obstáculo evidente.

ANÁLISE M5 (A IMAGEM M5 ESTÁ DISPONÍVEL):
- Compare o preço visível com a zona de interesse do M15.
- Identifique se o preço está FORA DA ZONA, NA ZONA ou se já se afastou dela.
- Para COMPRA: procure rejeição compradora, candle de confirmação e rompimento da máxima da confirmação.
- Para VENDA: procure rejeição vendedora, candle de confirmação e rompimento da mínima da confirmação.
- Distinga rejeição, confirmação e gatilho; não trate pavio isolado como gatilho suficiente.
- Procure falso rompimento/varredura de liquidez, estrutura local, e suporte/resistência próximo contra a operação.
- Dê uma zona refinada somente se os preços estiverem legíveis; ela deve ser uma faixa, não falsa precisão.
- Informe stop técnico/invalidação e alvo potencial apenas quando níveis visíveis sustentarem a estimativa.
- Se faltar evidência, responda AGUARDAR e diga o que precisa acontecer.
- A decisão é um plano condicional, não uma garantia de resultado.

FORMATO OBRIGATÓRIO:
Responda SOMENTE com JSON válido, sem markdown, sem ``` e sem texto antes/depois.
Use exatamente estas chaves:
{
  "h1": {
    "contexto": "",
    "estrutura": "",
    "fase": "",
    "principais_niveis": ""
  },
  "m15": {
    "contexto": "",
    "estrutura": "",
    "fase": "",
    "regiao_importante": "",
    "relacao_com_h1": ""
  },
  "direcao_a_procurar": "COMPRA | VENDA | AGUARDAR",
  "zona_de_interesse": "",
  "primeiro_obstaculo": "",
  "por_que_essa_zona": "",
  "m5": {
    "situacao_na_zona": "",
    "rejeicao": "",
    "confirmacao": "",
    "gatilho": "",
    "zona_refinada": "",
    "stop_tecnico": "",
    "alvo_potencial": "",
    "invalidacao": "",
    "zona_limite_inferior": null,
    "zona_limite_superior": null,
    "entrada_planejada": null,
    "stop_recomendado": null,
    "primeiro_obstaculo_preco": null,
    "margem_stop_explicacao": "",
    "risco_preco": null,
    "espaco_obstaculo_preco": null,
    "relacao_risco_retorno": null,
    "filtro_2_1": "APROVADO | REPROVADO | INDISPONIVEL",
    "obstaculos_proximos": "",
    "decisao": "AGUARDAR | GATILHO IDENTIFICADO | ENTRADA DESCARTADA",
    "justificativa": ""
  },
  "resultado": "",
  "confianca": "BAIXA | MÉDIA | ALTA"
}
'''

MODELS = [
    # Ordem pensada para priorizar disponibilidade e manter boa qualidade multimodal.
    ('gemini-3.7-flash', 2),
    ('gemini-3.8-flash', 2),
    ('gemini-3.5-flash-lite', 1),
]

REQUEST_TIMEOUT = 60


def retry_delay(response_headers, attempt):
    # Respeita Retry-After quando a API informar. Caso contrário, usa
    # um pequeno backoff para não martelar a API em caso de 503/429.
    try:
        retry_after = int(response_headers.get('Retry-After', '0'))
        if retry_after > 0:
            return min(retry_after, 8)
    except Exception:
        pass
    return 2 + (attempt * 3)


def calcular_filtro_rr(analise):
    """Calcula R:R com preços numéricos fornecidos pelo modelo; não inventa níveis."""
    m5 = analise.get('m5')
    if not isinstance(m5, dict):
        return analise

    def numero(chave):
        valor = m5.get(chave)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        return float(valor)

    entrada = numero('entrada_planejada')
    stop = numero('stop_recomendado')
    obstaculo = numero('primeiro_obstaculo_preco')
    inferior = numero('zona_limite_inferior')
    superior = numero('zona_limite_superior')
    direcao = str(analise.get('direcao_a_procurar', '')).upper()

    m5['risco_preco'] = None
    m5['espaco_obstaculo_preco'] = None
    m5['relacao_risco_retorno'] = None
    m5['filtro_2_1'] = 'INDISPONIVEL'

    if None in (entrada, stop, obstaculo, inferior, superior) or inferior >= superior:
        m5['filtro_2_1_motivo'] = 'Cotação da zona, entrada, stop ou primeiro obstáculo não está legível/confirmada.'
        return analise

    if direcao == 'COMPRA':
        stop_valido = stop < inferior
        obstaculo_valido = obstaculo > entrada
        risco = entrada - stop
        retorno = obstaculo - entrada
    elif direcao == 'VENDA':
        stop_valido = stop > superior
        obstaculo_valido = obstaculo < entrada
        risco = stop - entrada
        retorno = entrada - obstaculo
    else:
        m5['filtro_2_1_motivo'] = 'Direção não definida como COMPRA ou VENDA.'
        return analise

    if not stop_valido or not obstaculo_valido or risco <= 0 or retorno <= 0:
        m5['filtro_2_1_motivo'] = 'Níveis incompatíveis com a direção ou stop não está além de toda a zona.'
        return analise

    rr = retorno / risco
    m5['risco_preco'] = round(risco, 8)
    m5['espaco_obstaculo_preco'] = round(retorno, 8)
    m5['relacao_risco_retorno'] = round(rr, 2)
    m5['filtro_2_1'] = 'APROVADO' if rr >= 2.0 else 'REPROVADO'
    m5['filtro_2_1_motivo'] = (
        'Relação igual ou superior a 2:1 até o primeiro obstáculo.'
        if rr >= 2.0 else
        'Espaço até o primeiro obstáculo não oferece a relação mínima de 2:1.'
    )
    if rr < 2.0 and m5.get('decisao') == 'GATILHO IDENTIFICADO':
        m5['decisao'] = 'ENTRADA DESCARTADA'
    return analise


def gemini_analisar(h1_bytes, h1_type, m15_bytes, m15_type, m5_bytes, m5_type):
    chave = os.getenv('GEMINI_API_KEY', '').strip()
    if not chave:
        raise RuntimeError('GEMINI_API_KEY não configurada no servidor.')

    def part(data, mime):
        return {
            'inline_data': {
                'mime_type': mime or 'image/png',
                'data': base64.b64encode(data).decode('ascii')
            }
        }

    payload = {
        'contents': [{
            'parts': [
                {'text': GEMINI_PROMPT + '\n\nANALISE PRIMEIRO A IMAGEM H1 E DEPOIS A IMAGEM M15.\n\nIMAGEM H1:'},
                part(h1_bytes, h1_type),
                {'text': '\n\nIMAGEM M15:'},
                part(m15_bytes, m15_type),
                {'text': '\n\nIMAGEM M5 — analise rejeição, confirmação e gatilho com base somente nesta imagem:'},
                part(m5_bytes, m5_type),
            ]
        }],
        'generationConfig': {
            'temperature': 0.15,
            'responseMimeType': 'application/json'
        }
    }

    raw = json.dumps(payload).encode('utf-8')
    last_error = None

    for model, retries in MODELS:
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
        for attempt in range(retries):
            req = urllib.request.Request(
                url,
                data=raw,
                headers={
                    'Content-Type': 'application/json',
                    'x-goog-api-key': chave,
                    'User-Agent': 'IA-Analise-Graficos/1.0'
                },
                method='POST'
            )
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                    body = response.read().decode('utf-8')
                obj = json.loads(body)
                text = obj['candidates'][0]['content']['parts'][0]['text'].strip()
                if text.startswith('```'):
                    text = text.replace('```json', '', 1).replace('```', '', 1).strip()
                start = text.find('{')
                end = text.rfind('}')
                if start >= 0 and end > start:
                    text = text[start:end + 1]

                # Corrige a falha comum do modelo: vírgula antes de } ou ].
                # A expressão evita alterar vírgulas dentro de strings JSON.
                def remover_virgulas_finais(valor):
                    saida = []
                    dentro_string = False
                    escape = False
                    i = 0
                    while i < len(valor):
                        ch = valor[i]
                        if dentro_string:
                            saida.append(ch)
                            if escape:
                                escape = False
                            elif ch == '\\':
                                escape = True
                            elif ch == '"':
                                dentro_string = False
                            i += 1
                            continue
                        if ch == '"':
                            dentro_string = True
                            saida.append(ch)
                            i += 1
                            continue
                        if ch == ',':
                            j = i + 1
                            while j < len(valor) and valor[j].isspace():
                                j += 1
                            if j < len(valor) and valor[j] in '}]':
                                i += 1
                                continue
                        saida.append(ch)
                        i += 1
                    return ''.join(saida)

                try:
                    result = json.loads(text)
                except json.JSONDecodeError:
                    result = json.loads(remover_virgulas_finais(text))
                if not isinstance(result, dict):
                    raise ValueError('A resposta do Gemini não veio como objeto JSON.')
                return calcular_filtro_rr(result)

            except urllib.error.HTTPError as e:
                detail = e.read().decode('utf-8', errors='replace')
                last_error = f'{model} HTTP {e.code}: {detail[:700]}'

                # 429/5xx são transitórios. Tentamos novamente com backoff e,
                # depois, passamos ao próximo modelo da lista.
                if e.code in (429, 500, 502, 503, 504):
                    if attempt < retries - 1:
                        time.sleep(retry_delay(e.headers, attempt))
                        continue
                    break
                raise RuntimeError(last_error)

            except (urllib.error.URLError, TimeoutError) as e:
                last_error = f'{model}: {e}'
                if attempt < retries - 1:
                    time.sleep(retry_delay({}, attempt))
                    continue
                break

            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
                last_error = f'{model}: resposta inválida ({e})'
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                break

    raise RuntimeError(
        'Gemini temporariamente indisponível após tentativas nos modelos de reserva. '
        'Tente novamente em alguns segundos. Último detalhe: ' +
        (last_error or 'sem detalhe')
    )


M5_UPDATE_PROMPT = r'''Você é um analista técnico de Forex atualizando um plano já existente usando uma nova captura do M5.
Você receberá o JSON da análise principal H1/M15/M5 e uma NOVA imagem M5.
Não refaça nem apague o contexto H1/M15 original. Use-o como referência, mas avalie a situação atual do preço com honestidade.
Identifique se a zona antiga ainda vale, se houve rompimento, falso rompimento, pullback ou mudança da estrutura local. Não force a direção original se o preço a invalidou. Um movimento contrário no M5 pode ser correção, não declare reversão sem evidência.
Procure novas zonas refinadas somente se visíveis. Informe gatilho, stop técnico estrutural e STOP RECOMENDADO além de TODA a zona refinada com margem de segurança, alvo potencial e primeiro obstáculo.
Para compra, stop recomendado abaixo do limite inferior da zona; para venda, acima do limite superior. Informe cotações numéricas apenas quando legíveis; caso contrário use null.
Inclua zona_limite_inferior, zona_limite_superior, entrada_planejada, stop_recomendado, primeiro_obstaculo_preco e margem_stop_explicacao.
O servidor calculará R:R; não invente valores nem declare aprovação sem os preços. Se não houver evidência suficiente, AGUARDAR. O plano é condicional, não garantia.
Responda SOMENTE JSON válido com estas chaves: direcao_a_procurar, zona_de_interesse, primeiro_obstaculo, por_que_essa_zona, m5 (com situacao_na_zona, rejeicao, confirmacao, gatilho, zona_refinada, stop_tecnico, alvo_potencial, invalidacao, zona_limite_inferior, zona_limite_superior, entrada_planejada, stop_recomendado, primeiro_obstaculo_preco, margem_stop_explicacao, obstaculos_proximos, decisao, justificativa), resultado, confianca, resumo_atualizacao.
'''

def gemini_atualizar_m5(analise_principal, m5_bytes, m5_type):
    chave = os.getenv('GEMINI_API_KEY', '').strip()
    if not chave:
        raise RuntimeError('GEMINI_API_KEY não configurada no servidor.')
    parte = {'inline_data': {'mime_type': m5_type or 'image/png', 'data': base64.b64encode(m5_bytes).decode('ascii')}}
    payload = {
        'contents': [{'parts': [
            {'text': M5_UPDATE_PROMPT + '\n\nANÁLISE PRINCIPAL SALVA (JSON):\n' + json.dumps(analise_principal, ensure_ascii=False) + '\n\nNOVA IMAGEM M5 — use esta imagem como estado atual do preço:'},
            parte
        ]}],
        'generationConfig': {'temperature': 0.15, 'responseMimeType': 'application/json'}
    }
    raw = json.dumps(payload).encode('utf-8')
    last_error = None
    for model, retries in MODELS:
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
        for attempt in range(retries):
            req = urllib.request.Request(url, data=raw, headers={'Content-Type':'application/json','x-goog-api-key':chave,'User-Agent':'IA-Analise-Graficos/1.0'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                    obj = json.loads(response.read().decode('utf-8'))
                txt = obj['candidates'][0]['content']['parts'][0]['text'].strip()
                if txt.startswith('```'):
                    txt = txt.replace('```json','',1).replace('```','',1).strip()
                a, b = txt.find('{'), txt.rfind('}')
                if a >= 0 and b > a:
                    txt = txt[a:b+1]
                try:
                    upd = json.loads(txt)
                except json.JSONDecodeError:
                    txt = re.sub(r',\\s*([}\\]])', r'\\1', txt)
                    upd = json.loads(txt)
                if not isinstance(upd, dict) or not isinstance(upd.get('m5'), dict):
                    raise ValueError('Resposta de atualização sem o plano M5 esperado.')
                merged = dict(analise_principal)
                for key in ('direcao_a_procurar','zona_de_interesse','primeiro_obstaculo','por_que_essa_zona','resultado','confianca'):
                    if key in upd:
                        merged[key] = upd[key]
                merged['m5'] = upd['m5']
                merged = calcular_filtro_rr(merged)
                merged['resumo_atualizacao'] = upd.get('resumo_atualizacao', 'Plano M5 atualizado com a nova imagem.')
                return merged
            except urllib.error.HTTPError as e:
                last_error = f'{model} HTTP {e.code}: {e.read().decode("utf-8", errors="replace")[:500]}'
                if e.code in (429,500,502,503,504) and attempt < retries-1:
                    time.sleep(retry_delay(e.headers, attempt)); continue
                break
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as e:
                last_error = f'{model}: {e}'
                if attempt < retries-1:
                    time.sleep(2); continue
                break
    raise RuntimeError('Não foi possível atualizar o M5. Tente novamente. Detalhe: ' + (last_error or 'sem detalhe'))


HTML = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IA DE ANÁLISE MULTI-TIMEFRAME</title>
<style>
:root{--bg:#050B16;--panel:#081321;--panel2:#0B192A;--border:#183451;--cyan:#00D9FF;--blue:#1677FF;--purple:#A855F7;--magenta:#FF3DDE;--green:#00F59B;--red:#FF3158;--yellow:#FFD166;--text:#F4F8FF;--muted:#8EA5BE}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0%,#0b1930 0,#050B16 40%,#030711 100%);color:var(--text);font-family:Segoe UI,Arial,sans-serif;min-height:100vh}.wrap{max-width:1450px;margin:auto;padding:28px}.header{text-align:center;margin-bottom:24px}.title{font-size:38px;font-weight:800;letter-spacing:1px}.sub{color:var(--cyan);font-weight:600;margin-top:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:linear-gradient(180deg,#091525,#06101d);border:1px solid var(--border);border-radius:16px;overflow:hidden;box-shadow:0 0 30px #0008}.card.h1{border-color:#00d9ff88}.card.m15{border-color:#ff3dde88}.card.m5{border-color:#00f59b88}.head{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}.head b{font-size:18px}.tag{font-size:12px;color:var(--muted)}.body{padding:18px}.drop{height:310px;border:1px dashed #31506f;border-radius:12px;background:#06101c;display:flex;align-items:center;justify-content:center;overflow:hidden;cursor:pointer}.drop:hover{border-color:var(--cyan);box-shadow:inset 0 0 30px #00d9ff10}.drop img{max-width:100%;max-height:100%;object-fit:contain}.placeholder{text-align:center;color:var(--muted)}.placeholder strong{display:block;color:var(--text);font-size:17px;margin-bottom:6px}.actions{text-align:center;margin:20px 0}.btn{border:0;border-radius:10px;padding:13px 20px;font-weight:800;cursor:pointer;background:var(--green);color:#03100c;box-shadow:0 0 24px #00f59b22}.btn:disabled{opacity:.5;cursor:not-allowed}.status{color:var(--muted);font-size:13px;margin-top:10px}.analysis{grid-column:1/-1;border:1px solid var(--purple);background:linear-gradient(180deg,#091525,#060d19);border-radius:16px;box-shadow:0 0 30px #a855f722}.analysis .head{border-color:#a855f744}.result{padding:18px;display:none}.hero{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}.metric{padding:15px;border:1px solid var(--border);border-radius:12px;background:#07111f}.metric span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase}.metric strong{display:block;font-size:22px;margin-top:6px}.buy{color:var(--green)}.sell{color:var(--red)}.wait{color:var(--yellow)}.sections{display:grid;grid-template-columns:1fr 1fr;gap:12px}.box{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:15px}.box h3{margin:0 0 10px;color:var(--cyan);font-size:14px}.box p{margin:7px 0;color:#d9e5f5;line-height:1.45}.footer{text-align:center;color:var(--green);font-size:12px;margin-top:18px}.err{color:#ff8fa3;padding:18px;white-space:pre-wrap}.loading{color:var(--cyan);padding:18px;text-align:center}@media(max-width:900px){.grid,.sections{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.title{font-size:28px}.wrap{padding:14px}}
</style></head>
<body><div class="wrap">
<header class="header"><div class="title">IA DE ANÁLISE MULTI-TIMEFRAME</div><div class="sub">H1 → DIREÇÃO / CONTEXTO &nbsp; | &nbsp; M15 → REGIÃO / ESTRUTURA &nbsp; | &nbsp; M5 → REJEIÇÃO / CONFIRMAÇÃO / GATILHO</div></header>
<div class="grid">
<section class="card h1"><div class="head"><b>H1</b><span class="tag">DIREÇÃO / CONTEXTO</span></div><div class="body"><input id="h1" type="file" accept="image/*" hidden><div class="drop" id="dh1"><div class="placeholder"><strong>＋ ADICIONAR H1</strong>Clique aqui para selecionar o gráfico</div></div></div></section>
<section class="card m15"><div class="head"><b>M15</b><span class="tag">REGIÃO / ESTRUTURA</span></div><div class="body"><input id="m15" type="file" accept="image/*" hidden><div class="drop" id="dm15"><div class="placeholder"><strong>＋ ADICIONAR M15</strong>Clique aqui para selecionar o gráfico</div></div></div></section>
<section class="card m5"><div class="head"><b>M5</b><span class="tag">REJEIÇÃO / CONFIRMAÇÃO / GATILHO</span></div><div class="body"><input id="m5" type="file" accept="image/*" hidden><div class="drop" id="dm5"><div class="placeholder"><strong>＋ ADICIONAR M5</strong>Mostre a zona e os candles recentes</div></div></div></section>
<section class="card m5" style="border-color:#FFD16688"><div class="head"><b>ATUALIZAR M5</b><span class="tag">OPCIONAL · NOVO PLANO</span></div><div class="body"><input id="m5update" type="file" accept="image/*" hidden><div class="drop" id="dm5update"><div class="placeholder"><strong>＋ NOVA FOTO DO M5</strong>Atualize após rompimento, pullback ou mudança de estrutura</div></div><div class="status">Use depois da análise principal. H1 e M15 ficam salvos como referência nesta página.</div></div></section>
<div class="actions" style="grid-column:1/-1;display:flex;gap:12px;justify-content:center;align-items:center;flex-wrap:wrap"><button class="btn" id="go" disabled>ANALISAR H1 + M15 + M5</button><button class="btn" id="update" disabled style="background:var(--yellow)">ATUALIZAR SOMENTE M5</button><div class="status" id="status" style="width:100%">• SISTEMA PRONTO</div></div>
<section class="analysis"><div class="head"><b>ANÁLISE DA IA</b><span class="tag">GEMINI VISION</span></div><div id="out"><div class="loading">Adicione H1, M15 e M5 para montar o plano de entrada.</div></div></section>
</div><div class="footer">O plano M5 é condicional: confirme os níveis no gráfico e não trate a análise como garantia de resultado.</div></div>
<script>
let files={h1:null,m15:null,m5:null,m5update:null};
let analisePrincipal=null;
function setup(id,key,drop){const input=document.getElementById(id), box=document.getElementById(drop);box.onclick=()=>input.click();input.onchange=()=>{files[key]=input.files[0];show(box,input.files[0]);check()}}
function show(box,file){const r=new FileReader();r.onload=e=>box.innerHTML='<img src="'+e.target.result+'" alt="gráfico">';r.readAsDataURL(file)}
function check(){document.getElementById('go').disabled=!(files.h1&&files.m15&&files.m5);document.getElementById('update').disabled=!(analisePrincipal&&files.m5update)}
setup('h1','h1','dh1');setup('m15','m15','dm15');setup('m5','m5','dm5');setup('m5update','m5update','dm5update');
document.getElementById('go').onclick=async()=>{const btn=document.getElementById('go'),status=document.getElementById('status'),out=document.getElementById('out');btn.disabled=true;status.textContent='Enviando H1 + M15 + M5 para o Gemini...';out.innerHTML='<div class="loading">Analisando contexto, zona e plano de entrada M5...</div>';const fd=new FormData();fd.append('h1',files.h1);fd.append('m15',files.m15);fd.append('m5',files.m5);try{const r=await fetch('/analisar',{method:'POST',body:fd});const raw=await r.text();let d;try{d=JSON.parse(raw)}catch(_){throw new Error('O servidor retornou uma página de erro em vez de JSON. Tente novamente em alguns segundos.\n\nDetalhe: '+raw.slice(0,180))}if(!r.ok)throw new Error(d.error||'Erro na análise');analisePrincipal=d;render(d);status.textContent='• ANÁLISE PRINCIPAL SALVA — M5 PODE SER ATUALIZADO'}catch(e){out.innerHTML='<div class="err">Erro na análise Gemini:\n'+e.message+'</div>';status.textContent='• ERRO NA ANÁLISE'}finally{btn.disabled=false;check()}};
document.getElementById('update').onclick=async()=>{
 const btn=document.getElementById('update'),mainBtn=document.getElementById('go'),status=document.getElementById('status'),out=document.getElementById('out');
 if(!analisePrincipal){status.textContent='Faça primeiro a análise principal H1 + M15 + M5.';return}
 btn.disabled=true;mainBtn.disabled=true;status.textContent='Atualizando o plano com a nova imagem M5...';
 const fd=new FormData();fd.append('m5_update',files.m5update);fd.append('analise_principal',JSON.stringify(analisePrincipal));
 try{const r=await fetch('/atualizar_m5',{method:'POST',body:fd});const raw=await r.text();let d;try{d=JSON.parse(raw)}catch(_){throw new Error('O servidor retornou uma página de erro. Tente novamente. Detalhe: '+raw.slice(0,180))}if(!r.ok)throw new Error(d.error||'Erro ao atualizar M5');analisePrincipal=d;render(d);status.textContent='• M5 ATUALIZADO — CONTEXTO H1/M15 PRESERVADO';files.m5update=null;document.getElementById('m5update').value='';document.getElementById('dm5update').innerHTML='<div class="placeholder"><strong>＋ NOVA FOTO DO M5</strong>Selecione outra captura para atualizar novamente</div>';check();
 }catch(e){out.innerHTML+='<div class="err">Erro ao atualizar M5:\\n'+e.message+'</div>';status.textContent='• ERRO NA ATUALIZAÇÃO'}finally{btn.disabled=!(analisePrincipal&&files.m5update);mainBtn.disabled=!(files.h1&&files.m15&&files.m5)}
};
function render(d){
 const dir=(d.direcao_a_procurar||'AGUARDAR').toUpperCase();
 const cls=dir==='COMPRA'?'buy':dir==='VENDA'?'sell':'wait';
 const esc=x=>String(x??'—').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
 const m=d.m5||{};
 const card=(title,body)=>'<div class="box"><h3>'+title+'</h3>'+body+'</div>';
 const line=(label,value)=>'<p><b>'+label+':</b> '+esc(value)+'</p>';
 document.getElementById('out').innerHTML='<div class="result" style="display:block"><div class="hero"><div class="metric"><span>Direção a procurar</span><strong class="'+cls+'">'+esc(dir)+'</strong></div><div class="metric"><span>Zona de interesse M15</span><strong>'+esc(d.zona_de_interesse)+'</strong></div><div class="metric"><span>Primeiro obstáculo</span><strong>'+esc(d.primeiro_obstaculo)+'</strong></div></div><div class="sections">'+
 card('H1 — CONTEXTO',line('Contexto',d.h1?.contexto)+line('Estrutura',d.h1?.estrutura)+line('Fase',d.h1?.fase)+line('Níveis',d.h1?.principais_niveis))+
 card('M15 — ESTRUTURA / REGIÃO',line('Contexto',d.m15?.contexto)+line('Estrutura',d.m15?.estrutura)+line('Fase',d.m15?.fase)+line('Região',d.m15?.regiao_importante)+line('Relação com H1',d.m15?.relacao_com_h1))+
 card('POR QUE ESSA ZONA','<p>'+esc(d.por_que_essa_zona)+'</p>')+
 card('M5 — PLANO DE ENTRADA',line('Decisão',m.decisao)+line('Situação na zona',m.situacao_na_zona)+line('Rejeição',m.rejeicao)+line('Confirmação',m.confirmacao)+line('Gatilho',m.gatilho)+line('Zona refinada',m.zona_refinada)+line('Stop técnico estrutural',m.stop_tecnico)+line('Stop recomendado (cotação exata)',m.stop_recomendado)+line('Margem do stop',m.margem_stop_explicacao)+line('Entrada planejada',m.entrada_planejada)+line('Primeiro obstáculo (cotação)',m.primeiro_obstaculo_preco)+line('Limites da zona',String(m.zona_limite_inferior??'—')+' até '+String(m.zona_limite_superior??'—'))+line('Risco em preço',m.risco_preco)+line('Espaço até obstáculo',m.espaco_obstaculo_preco)+line('Relação risco-retorno',m.relacao_risco_retorno)+line('Filtro mínimo 2:1',m.filtro_2_1)+line('Motivo do filtro',m.filtro_2_1_motivo)+line('Alvo potencial',m.alvo_potencial)+line('Invalidação',m.invalidacao)+line('Obstáculos próximos',m.obstaculos_proximos)+line('Justificativa',m.justificativa))+
 card('RESULTADO E CONFIANÇA',line('Resumo',d.resultado)+line('Confiança visual',d.confianca))+'</div></div>';
}
</script></body></html>'''

@app.get('/')
def index():
    return render_template_string(HTML)

@app.post('/analisar')
def analisar():
    h1 = request.files.get('h1')
    m15 = request.files.get('m15')
    m5 = request.files.get('m5')
    if not h1 or not m15 or not m5:
        return jsonify(error='Envie as três imagens: H1, M15 e M5.'), 400
    try:
        result = gemini_analisar(h1.read(), h1.mimetype, m15.read(), m15.mimetype, m5.read(), m5.mimetype)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.post('/atualizar_m5')
def atualizar_m5():
    imagem = request.files.get('m5_update')
    analise_raw = request.form.get('analise_principal', '')
    if not imagem:
        return jsonify(error='Envie uma nova imagem M5.'), 400
    try:
        principal = json.loads(analise_raw)
        if not isinstance(principal, dict) or not isinstance(principal.get('h1'), dict) or not isinstance(principal.get('m15'), dict):
            return jsonify(error='A análise principal não está válida. Faça novamente H1 + M15 + M5.'), 400
        result = gemini_atualizar_m5(principal, imagem.read(), imagem.mimetype)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify(error='Não foi possível ler a análise principal salva. Faça uma nova análise completa.'), 400
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.errorhandler(413)
def too_large(_e):
    return jsonify(error='As imagens são muito grandes. Use imagens de até 50 MB no total.'), 413

@app.errorhandler(500)
def internal_error(_e):
    return jsonify(error='Erro interno no servidor durante a análise. Tente novamente.'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=False)
