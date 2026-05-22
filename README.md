# Robo de contatos publicos de prefeituras

Projeto Python para coletar contatos publicos institucionais em sites oficiais de prefeituras municipais brasileiras e gerar uma planilha Excel final para a Point C / Eduardo.

O sistema foi pensado para receber uma base local de municipios, filtrar o escopo acordado, acessar sites oficiais informados ou inferidos com cautela, consultar fontes estaduais configuradas quando aplicavel, extrair contatos publicos associados a cargos/orgaos e registrar pendencias quando os dados nao estiverem disponiveis.

## Escopo

Dados buscados:

- prefeito;
- vice-prefeito;
- chefe de gabinete;
- desenvolvimento economico;
- desenvolvimento;
- financas/fazenda;
- planejamento;
- agencias municipais de desenvolvimento;
- sala do empreendedor ou orgao equivalente.

Campos finais:

- UF;
- Estado;
- Municipio/Capital;
- Municipio;
- Populacao;
- Criterio de inclusao;
- Esfera;
- Site oficial;
- Orgao/Secretaria;
- Cargo/Area;
- Cargo/Orgao;
- Nome;
- E-mail;
- Telefone;
- Celular/WhatsApp;
- Celular;
- URL da fonte;
- URL especifica;
- Data da coleta;
- Status;
- Observacoes.

## Criterios de municipios

- SP: municipios com populacao acima de 30.000 habitantes e capital incluida.
- MG, SC, PR, RS, RJ, GO, ES, BA e SE: municipios com populacao acima de 15.000 habitantes e capitais incluidas.
- Demais UFs e DF: apenas capitais.

Os criterios ficam em `config/estados.yml`.

## Instalacao

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Em Linux/macOS, ative o ambiente com:

```bash
source .venv/bin/activate
```

Playwright e opcional para paginas dinamicas. Para habilitar:

```bash
pip install -e ".[dynamic]"
playwright install chromium
```

## Base IBGE/local

Coloque a base em um destes caminhos:

- `data/input/municipios_ibge.xlsx`
- `data/input/municipios_ibge.csv`

Colunas aceitas com nomes flexiveis:

- municipio: `municipio`, `município`, `nome_municipio`, `nome do município`;
- UF/Estado: `uf`, `estado`;
- populacao: `populacao`, `população`, `habitantes`;
- capital: `capital`, `is_capital`, `capital_do_estado`;
- site oficial: `site`, `site_oficial`, `url`, `prefeitura_url`.

Se nao houver base real, o arquivo `data/input/exemplo_municipios.csv` permite testar o funcionamento. Ele nao deve ser usado como resultado final real.

Para gerar uma lista nacional congelada a partir do IBGE/SIDRA:

```bash
python -m src.gerar_lista_congelada --ano 2025 --output data/input/municipios_ibge_escopo_congelado.csv
```

O arquivo gerado inclui codigo IBGE, municipio, UF, estado, populacao, capital, criterio de inclusao, fonte e data de congelamento.

## Como executar

Com base real:

```bash
python -m src.main --input data/input/municipios_ibge.xlsx --output data/output/resultado_final_point_c.xlsx
```

Somente filtrar municipios:

```bash
python -m src.main --input data/input/municipios_ibge.xlsx --somente-filtrar
```

Teste com a base de exemplo:

```bash
python -m src.main --input data/input/exemplo_municipios.csv --somente-filtrar
```

Opcoes uteis:

```bash
python -m src.main --limite 10
python -m src.main --uf SP
python -m src.main --municipio "Campinas"
python -m src.main --dry-run
python -m src.main --sem-playwright
python -m src.main --sem-estaduais
```

## Configuracao de cargos e secretarias

Edite `config/cargos.yml` para incluir, remover ou alterar cargos, orgaos e variacoes de texto.

Exemplo:

```yaml
planejamento:
  - planejamento
  - secretaria de planejamento
  - planejamento urbano
```

As palavras usadas para selecionar links internos ficam em `config/palavras_chave.yml`.

As fontes estaduais ficam em `config/governos_estaduais.yml`. Elas so sao consultadas por URL explicita configurada; o robo nao infere portais estaduais automaticamente.

As regras de timeout, retries, delay, limite de paginas e user-agent ficam em `config/scraping.yml`.

## Saida Excel

Arquivo final padrao:

```text
data/output/resultado_final_point_c.xlsx
```

Abas geradas:

- `Resultado consolidado`: contatos encontrados, parciais ou pendencias por municipio.
- `Municípios pesquisados`: status geral por municipio processado.
- `Pendências`: sites ausentes, sites fora do ar, bloqueios, contatos nao encontrados e validacoes.
- `Resumo`: indicadores consolidados da execucao.
- `Fontes e Log`: URLs consultadas, URL final, status, HTTP, metodo, data/hora e observacoes.
- `Configuração`: cargos, palavras-chave, parametros de scraping, criterios de estados e fontes estaduais.

A planilha congela a primeira linha, aplica filtro, ajusta larguras e destaca cabecalhos.

## Logs

Os logs ficam em:

```text
logs/execucao.log
```

Eles registram inicio/fim, municipio processado, URL acessada, paginas ignoradas, erros, dados encontrados e pendencias.

## Status possiveis

- Encontrado
- Parcial
- Não encontrado
- Não publicado
- Site fora do ar
- Site não localizado
- Página sem informação pública
- Bloqueio técnico
- Necessita validação manual

## Limitacoes conhecidas

O projeto nao promete encontrar 100% dos dados. A coleta depende do que cada prefeitura publica em seu site oficial.

- Sites fora do ar sao marcados como pendencia.
- Sites com captcha ou bloqueio sao marcados como bloqueio tecnico.
- Sites acessiveis sem contatos especificos publicados sao marcados como nao publicado ou parcial.
- Dados publicados incorretamente pela prefeitura sao registrados conforme a fonte disponivel.
- Contatos genericos sao marcados como contato geral quando nao houver associacao clara a cargo especifico.
- O robo nao burla login, captcha, paywall ou protecao tecnica.

## Regras eticas de scraping

- Coletar apenas dados publicos em paginas oficiais ou institucionais.
- Nao usar tecnicas agressivas.
- Respeitar timeouts, retries moderados e delay entre requisicoes.
- Usar user-agent identificavel.
- Registrar sempre a URL de origem do dado.
- Nao inventar dados.
- Registrar pendencias quando houver ambiguidade ou ausencia de informacao.

## Testes

```bash
pytest
python -m src.main --help
```
